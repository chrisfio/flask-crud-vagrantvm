from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import cgi
from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from models import Base, Spirit, Recipe 
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)

# Connect to Database and create database session
engine = create_engine('sqlite:///drinkcatalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# Show all spirits
@app.route('/')
@app.route('/spirit/')
@app.route('/spirits/')
def showSpirits():
    spirits = session.query(Spirit).order_by(asc(Spirit.name))
    return render_template('publicSpirits.html', spirits=spirits)


# Add a new spirit category
@app.route('/spirits/new/', methods=['GET', 'POST'])
def newSpirit():
    if request.method == 'POST':
        newSpirit = Spirit(
            name= request.form['name'], 
            description = request.form['description'])
        session.add(newSpirit)
        flash('New Spirit %s Successfully Added' % newSpirit.name)
        session.commit()
        return redirect(url_for('showSpirits'))
    else:
        return render_template('newSpirit.html')

# Edit a spirit
@app.route('/spirit/<int:spirit_id>/edit/', methods=['GET', 'POST'])
@app.route('/spirits/<int:spirit_id>/edit/', methods=['GET', 'POST'])
def editSpirit(spirit_id):
    editedSpirit = session.query(
        Spirit).filter_by(id=spirit_id).one()
#    if 'username' not in login_session:
#        return redirect('/login')
#    if editedSpirit.user_id != login_session['user_id']:
#        return "<script>function myFunction() {alert('You are not authorized to edit this spirit. Please create your own spirit in order to edit.');}</script><body onload='myFunction()'>"
    if request.method == 'POST':
        if request.form['name']:
            editedSpirit.name = request.form['name']
            flash('Spirit Successfully Edited %s' % editedSpirit.name)
            return redirect(url_for('showSpirits'))
    else:
        return render_template('editSpirit.html', spirit=editedSpirit)


# Delete a restaurant
@app.route('/spirit/<int:spirit_id>/delete/', methods=['GET', 'POST'])
@app.route('/spirits/<int:spirit_id>/delete/', methods=['GET', 'POST'])
def deleteSpirit(spirit_id):
    spiritToDelete = session.query(
        Spirit).filter_by(id=spirit_id).one()
#    if 'username' not in login_session:
#        return redirect('/login')
#    if spirittToDelete.user_id != login_session['user_id']:
#        return "<script>function myFunction() {alert('You are not authorized to delete this spirit. Please create your own spirit in order to delete.');}</script><body onload='myFunction()'>"
    if request.method == 'POST':
        session.delete(spiritToDelete)
        flash('%s Successfully Deleted' % spiritToDelete.name)
        session.commit()
        return redirect(url_for('showSpirits', spirit_id=spirit_id))
    else:
        return render_template('deleteSpirit.html', spirit=spiritToDelete)


# View recipes using a particular spirit
@app.route('/spirit/<int:spirit_id>/')
@app.route('/spirits/<int:spirit_id>/')
@app.route('/spirit/<int:spirit_id>/cocktails/')
@app.route('/spirits/<int:spirit_id>/cocktails/')
def showRecipes(spirit_id):
    spirit = session.query(Spirit).filter_by(id=spirit_id).one()
#    creator = getUserInfo(spirit.user_id)
    recipes = session.query(Recipe).filter_by(
        spirit_id=spirit_id).all()
#    if 'username' not in login_session or creator.id != login_session['user_id']:
 #       return render_template('TBDpublicmenu.html', recipes=recipes, spirit=spirit, creator=creator)
 #   else:
    return render_template('recipes.html', recipes=recipes, spirit=spirit) #, creator=creator)

# Create a new recipe
@app.route('/spirit/<int:spirit_id>/cocktails/new/', methods=['GET', 'POST'])
@app.route('/spirits/<int:spirit_id>/cocktails/new/', methods=['GET', 'POST'])
def newRecipe(spirit_id):
#    if 'username' not in login_session:
#        return redirect('/login')
    spirit = session.query(Spirit).filter_by(id=spirit_id).one()
#    if login_session['user_id'] != restaurant.user_id:
#        return "<script>function myFunction() {alert('You are not authorized to add menu items to this restaurant. Please create your own restaurant in order to add items.');}</script><body onload='myFunction()'>"
    if request.method == 'POST':
        newRecipe = Recipe(name=request.form['name'], description=request.form['description'], ingredients=request.form[
        	'ingredients'], instructions=request.form['instructions'], spirit_id=spirit_id) #, user_id=spirit.user_id)
        session.add(newRecipe)
        session.commit()
        flash('New Menu %s Item Successfully Created' % (newRecipe.name))
        return redirect(url_for('showRecipes', spirit_id=spirit_id))
    else:
        return render_template('newRecipe.html', spirit=spirit)


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
