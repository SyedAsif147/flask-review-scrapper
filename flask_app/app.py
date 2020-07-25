from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine
import os
from functools import wraps
import pandas as pd
from wtforms import SelectField
from flask_wtf import FlaskForm
import numpy as np
import requests
from bs4 import BeautifulSoup
import pandas as pd
from lxml import html
import re

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))

app.config['SECRET_KEY'] = 'sakjnfksmfoknfijanfkanmokgmokmfgow76y892inf3ih2982i'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'+os.path.join(basedir,'details.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], echo=False)
db = SQLAlchemy(app)

data={}

def gen_unique(data):
    data1 = np.array(data)
    return np.unique(data1)

# database models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(80))
    
class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(100))
    city = db.Column(db.String(100))
    locality = db.Column(db.String(100))
    link = db.Column(db.String(300))

# Form 
class Form(FlaskForm):
    state = SelectField('state', choices=list(gen_unique([i.state for i in Location.query.all()])))
    city = SelectField('city', choices=[])
    locality = SelectField('locality', choices=[])

# creating decorator
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if session['login']==True:
            return f(*args, **kwargs)
        else:
            flash("You need to login first", "danger")
            return redirect(url_for('login'))

    return wrap

# Review Request

header={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
    "Accept-Encoding": "*",
    "Connection": "keep-alive",
    "Accept": "application/json", 
    "user-key": "API_KEY"
    }

def scrapper_links(link):
    links=[]
    with requests.Session() as s:

        nums=6
        i=1
        while i<nums:

            url=s.get("{}?page={}&sort=best&nearby=0".format(link,i),headers=header)
            url_content=url.content
            soup=BeautifulSoup(url_content,"html.parser")
            div=soup.find("div",attrs={"class":"col-l-4 mtop pagination-number"})
            num =int(div.text.split("of")[-1])
            if num<nums:
                nums=num+1
            else:
                nums=6
            a=soup.find_all("a",attrs={"data-result-type":"ResCard_Name"})
            for k in a:
                links.append(k["href"])
            i=i+1
    links=list(set(links))
    return links

def scrapper_output(links):
    output=[]
    with requests.Session() as s:
        for i in links:
            result=[]
            # print(i)
            j=1
            t=1
            while(t!=0):
            
                #print(i,j)
                url=s.get(i+"/reviews?page={}&sort=dd&filter=reviews-dd".format(j),headers=header)
                url_content=url.content
                soup=BeautifulSoup(url_content,"html.parser")
                # review=soup.find_all()

                button=soup.find_all("button",attrs={"class":"sc-1kx5g6g-1 elxuhW sc-jUiVId hMOkj"})
                if "Add Review" in [i.text for i in button]:
                    break

                r=soup.find_all("p")
                a=soup.find_all("a")
                if "Chevron Right iconIt is an icon with title Chevron Rightchevron-right" in [i.text for i in a] : 
                    t=1
                else:
                    t=0
                content=""
            
                for m in r:
                    content=content+"\n"+m.text
                main=content[content.find("Newest First")+len("Newest First")+1:]
                #print(len( main.split("Comment")[:-1]))
                main = re.sub(r"Comment[s]+", "Comment",main)
                #print(main)
                for k in main.split("Comment")[:-1]:
                    data=k.strip().split("\n")
                    name=data[0]
                    rate=data[1]
                    review="\n".join(data[3:-1])
                    #print(name)
                    result.append({"name":data[0],"rate":data[1],"review":"\n".join(data[3:-1])})
                #print(result)
                j+=1
            output.append({i.split("/")[-1]:result}) # Ouput for another code
            #pd.DataFrame(result).to_csv("Review_Again/"+i.split("/")[-1]+".csv")   
    return output



# routes - views
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == "POST":
        uname = request.form['uname']
        mail = request.form['mail']
        passw = request.form['passw']
        register = User(username = uname, email = mail, password = generate_password_hash(passw))
        db.session.add(register)
        db.session.commit()

        return redirect(url_for('login'))
    return render_template("register.html")

@app.route('/login/', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uname = request.form["uname"]
        passw = request.form["passw"]
        
        login = User.query.filter_by(username=uname).first()
        if login is not None:
            if check_password_hash(login.password, passw):
                session['login'] = True
                session['username'] = login.username
                session['email'] = login.email
                flash('Welcome ' + session['username'] +'! You have been successfully logged in', 'success')
                return redirect(url_for("index"))
            else:
                flash('Password does not match', 'danger')
                return render_template('login.html')
        else:
            flash('User does not exist', 'danger')
    return render_template("login.html")

@app.route('/logout/')
@login_required
def logout():
    session['login']=False
    session.pop('username')
    session.pop('email')
    flash("You have been logged out", 'info')
    return redirect(url_for('login'))

@app.route("/form-data", methods=['GET','POST'])
@login_required
def index():
    form = Form()
    cities=[]
    localities=[]
    if request.method == 'POST':
        state = request.form.get('state')
        city = request.form.get('city')
        locality = request.form.get('locality')
        cities = [i.city for i in Location.query.filter_by(state=state).all()]
        form.city.choices = list(gen_unique(cities))
        localities = [j.locality for j in Location.query.filter_by(city=city).all()]
        form.locality.choices = list(gen_unique(localities))
        data['state']=state
        data['city']=city
        data['locality']=locality
        if data['locality'] != None:
            loc=Location.query.filter_by(state=data['state'] , city=data['city'] , locality=data['locality'])
            session['link'] = loc[0].link
            return redirect(url_for('scrap_data'))
    return render_template('index.html', form=form)

@app.route("/output-gen/", methods=['GET'])
def scrap_data():
    link = session.get('link', None)
    links = scrapper_links(link)
    output = scrapper_output(links)
    return jsonify(output)

@app.route("/")
def home():
    return render_template('home.html')

if __name__ == "__main__":
    app.run(debug=True)

