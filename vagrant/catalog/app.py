from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from flask import Flask, render_template, request, redirect, jsonify, url_for, flash, make_response
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from models import Base, Spirit, Recipe 
from flask import session as login_session
import random, string, httplib2, json, requests, cgi
from oauth2client.client import flow_from_clientsecrets, FlowExchangeError


app = Flask(__name__)

# Connect to Database and create database session
engine = create_engine('sqlite:///drinkcatalog.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Create anti-forgery state token
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets_google.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output


# Disconnect from Google login
@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session.get('access_token')
    if access_token is None:
        print 'Access Token is None'
        response = make_response(json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['username']
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        response = make_response(json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response






# NEED TO UPDATE
# JSON APIs to view Restaurant Information
@app.route('/restaurant/<int:restaurant_id>/menu/JSON')
def restaurantMenuJSON(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    items = session.query(MenuItem).filter_by(
        restaurant_id=restaurant_id).all()
    return jsonify(MenuItems=[i.serialize for i in items])


@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/JSON')
def menuItemJSON(restaurant_id, menu_id):
    Menu_Item = session.query(MenuItem).filter_by(id=menu_id).one()
    return jsonify(Menu_Item=Menu_Item.serialize)


@app.route('/restaurant/JSON')
def restaurantsJSON():
    restaurants = session.query(Restaurant).all()
    return jsonify(restaurants=[r.serialize for r in restaurants])


# Create user
def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None

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
    return render_template('recipeList.html', recipes=recipes, spirit=spirit) #, creator=creator)

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
        newRecipe = Recipe(
        	name=request.form['name'], 
        	description=request.form['description'], 
        	ingredients=request.form['ingredients'], 
        	instructions=request.form['instructions'], 
        	spirit_id=spirit_id) 
        	#, user_id=spirit.user_id)
        session.add(newRecipe)
        session.commit()
        flash('New Menu %s Item Successfully Created' % (newRecipe.name))
        return redirect(url_for('showRecipes', spirit_id=spirit_id))
    else:
        return render_template('newRecipe.html', spirit=spirit)


# Edit a recipe
@app.route('/spirit/<int:spirit_id>/cocktail/<int:recipe_id>/edit', methods=['GET', 'POST'])
@app.route('/spirit/<int:spirit_id>/cocktails/<int:recipe_id>/edit', methods=['GET', 'POST'])
@app.route('/spirits/<int:spirit_id>/cocktail/<int:recipe_id>/edit', methods=['GET', 'POST'])
@app.route('/spirits/<int:spirit_id>/cocktails/<int:recipe_id>/edit', methods=['GET', 'POST'])
def editRecipe(spirit_id, recipe_id):
#    if 'username' not in login_session:
 #       return redirect('/login')
    editedRecipe = session.query(Recipe).filter_by(id=recipe_id).one()
    spirit = session.query(Spirit).filter_by(id=spirit_id).one()
#    if login_session['user_id'] != restaurant.user_id:
#        return "<script>function myFunction() {alert('You are not authorized to edit menu items to this restaurant. Please create your own restaurant in order to edit items.');}</script><body onload='myFunction()'>"
    if request.method == 'POST':
        if request.form['name']:
            editedRecipe.name = request.form['name']
        if request.form['description']:
            editedRecipe.description = request.form['description']
        if request.form['ingredients']:
            editedRecipe.ingredients = request.form['ingredients']
        if request.form['instructions']:
            editedRecipe.instructions = request.form['instructions']
        session.add(editedRecipe)
        session.commit()
        flash('Recipe Successfully Edited')
        return redirect(url_for('showRecipes', spirit_id=spirit_id))
    else:
        return render_template('editRecipe.html', spirit_id=spirit_id, recipe_id=recipe_id, recipe=editedRecipe)


# Edit a recipe
@app.route('/spirit/<int:spirit_id>/cocktail/<int:recipe_id>/delete', methods=['GET', 'POST'])
@app.route('/spirit/<int:spirit_id>/cocktails/<int:recipe_id>/delete', methods=['GET', 'POST'])
@app.route('/spirits/<int:spirit_id>/cocktail/<int:recipe_id>/delete', methods=['GET', 'POST'])
@app.route('/spirits/<int:spirit_id>/cocktails/<int:recipe_id>/delete', methods=['GET', 'POST'])
def deleteRecipe(spirit_id, recipe_id):
#    if 'username' not in login_session:
 #       return redirect('/login')
    deleteRecipe = session.query(Recipe).filter_by(id=recipe_id).one()
    spirit = session.query(Spirit).filter_by(id=spirit_id).one()
#    if login_session['user_id'] != restaurant.user_id:
#        return "<script>function myFunction() {alert('You are not authorized to edit menu items to this restaurant. Please create your own restaurant in order to edit items.');}</script><body onload='myFunction()'>"
    if request.method == 'POST':
        session.delete(deleteRecipe)
        session.commit()
        flash('%s Recipe Successfully Deleted' % deleteRecipe.name)
        return redirect(url_for('showRecipes', spirit_id=spirit_id))
    else:
        return render_template('deleteRecipe.html', spirit_id=spirit_id, recipe_id=recipe_id, recipe=deleteRecipe)



if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
