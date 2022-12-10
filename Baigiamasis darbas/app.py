from flask import Flask, request, session, flash, redirect, url_for, render_template, send_file
from flask_sqlalchemy import SQLAlchemy
import uuid
import os
import jwt
from werkzeug.utils import secure_filename
import json
import datetime
from functools import wraps
import requests


app = Flask(__name__)

app.config["SECRET_KEY"] = "secretkey"
app.config["SQLALCHEMY_DATABASE_URI"] = 'sqlite:///../tmp/database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

UPLOAD_FOLDER = './static'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(50))
    password = db.Column(db.String(80))
    admin = db.Column(db.Boolean)


class Notes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50))
    text = db.Column(db.String(50))
    category = db.Column(db.String(50))
    label = db.Column(db.String(50))
    picture = db.Column(db.String(50))


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(50))


def __repr__(self):
    return f'<User {self.name}>'


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):

        if session.get('token') == True:
            flash('No token given')
            return redirect(url_for('login'))

        if "token" in session:
            token = session["token"]
            try:
                data = jwt.decode(
                    token, app.config['SECRET_KEY'], algorithms=["HS256"])
                current_user = User.query.filter_by(
                    public_id=data['public_id']).first()
            except:
                flash('token is invalid')
                return redirect(url_for('logout'))

        return f(current_user, *args, **kwargs)
    return decorated


@app.route('/', methods=['GET'])
def home():
    if "token" in session:
        token = session["token"]
        return render_template('homeLogin.html')

    return render_template('home.html')


@app.route('/register', methods=['GET', 'POST'])
def register():

    if "token" in session:
        token = session["token"]
        return redirect(url_for("home"))

    else:
        if request.method == 'POST':
            names = request.form['username']
            password = request.form['password']
            user = User.query.filter_by(name=names).first()
            try:
                if names == user.name:
                    flash('Thee is already an user with that name')
                    return render_template("register.html")
            except:
                new_user = User(public_id=str(uuid.uuid4()),
                                name=names, password=password, admin=False)
                db.session.add(new_user)
                db.session.commit()
                flash('Thank for registering!!!')
                return redirect(url_for("home"))
        return render_template("register.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if "token" in session:
        token = session["token"]
        return redirect(url_for("home"))

    else:
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            user = User.query.filter_by(name=username).first()

            if not user:
                flash('Wrong username or password!')
                return render_template("login.html")

            if user.password != password:
                flash('Wrong username or password!')
                return render_template("login.html")

            token = jwt.encode({'public_id': user.public_id, 'exp': datetime.datetime.utcnow(
            ) + datetime.timedelta(minutes=45)}, app.config['SECRET_KEY'], "HS256")
            session.permanent = True
            session["token"] = token
            flash("Login successful")

            return redirect(url_for('home'))

    return render_template("login.html")


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('token', None)
    return redirect(url_for('home'))


@app.route('/notes', methods=['GET'])
@token_required
def notes(current_user):
    if "token" in session:
        token = session["token"]

        allCategorys = Category.query.filter_by(
            name=current_user.public_id).all()
        allNotes = Notes.query.filter_by(public_id=current_user.public_id).all()

        notesOutput = []
        for note in allNotes:
            newNote = {}
            newNote['text'] = note.text
            newNote['id'] = note.id
            newNote['category'] = note.category
            newNote['label'] = note.label
            notesOutput.append(newNote)

        output = []
        for category in allCategorys:
            newCategory = {}
            newCategory['id'] = category.id
            newCategory['category'] = category.category
            newCategory['name'] = category.name
            output.append(newCategory)

        return render_template("notes.html", output=output, len=len(output), lenNotes=len(notesOutput), notesOutput=notesOutput, current_user=current_user)
    return redirect(url_for("login"))


@app.route('/category', methods=["POST"])
@token_required
def category(current_user):
    if "token" in session:
        token = session["token"]
        if request.method == 'POST':
            addNewCategory = request.form['add-new-category']
            newNote = Category(category=addNewCategory,
                               name=current_user.public_id)
            db.session.add(newNote)
            db.session.commit()

        return redirect(url_for('notes'))
    return redirect(url_for('notes'))


@app.route('/notes/<newUserCategory>', methods=["GET"])
@token_required
def userCreatedCategory(current_user, newUserCategory):
    if "token" in session:
        token = session["token"]
        allCategorys = Category.query.filter_by(name=current_user.public_id).all()
        allNotes = Notes.query.filter_by(public_id=current_user.public_id, category=newUserCategory).all()

        notesOutput = []
        for note in allNotes:
            newNote = {}
            newNote['text'] = note.text
            newNote['id'] = note.id
            newNote['category'] = note.category
            newNote['label'] = note.label
            notesOutput.append(newNote)

        output = []
        for category in allCategorys:
            newCategory = {}
            newCategory['id'] = category.id
            newCategory['category'] = category.category
            newCategory['name'] = category.name
            output.append(newCategory)

        return render_template('specificNotes.html', output=output, len=len(output), newUserCategory=newUserCategory,
        lenNotes=len(notesOutput), notesOutput=notesOutput)

    return redirect(url_for('login'))


@app.route('/notes/<newUserCategory>', methods=["POST"])
@token_required
def createNewNote(current_user, newUserCategory):

    text = request.form['text']
    file = request.files['file']
    label = request.form['label']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    newNote = Notes(category=newUserCategory, public_id=current_user.public_id,
                    text=text, label=label, picture=file.filename)
    db.session.add(newNote)
    db.session.commit()
    return redirect(url_for('userCreatedCategory', newUserCategory=newUserCategory))

@app.route('/notes/<newUserCategory>/<id>', methods=["GET"])
@token_required
def individualCategoryNote(current_user, newUserCategory, id):
    oneNote = Notes.query.filter_by(id=id, public_id=current_user.public_id).first()

    return render_template('singleNote.html', newUserCategory=newUserCategory, oneNote=oneNote)

# Edit , Delete rest calls
@app.route('/notes/delete/picture/<id>', methods=["POST"])
@token_required
def deletePicture(current_user, id):

    note = Notes.query.filter_by(id=id, public_id=current_user.public_id).first()
    note.picture = '1'
    db.session.commit()

    return redirect(f'/notes/{note.category}/{id}')

@app.route('/notes/delete/<id>', methods=["POST"])
@token_required
def deletenote(current_user, id):
    note = Notes.query.filter_by(id=id, public_id=current_user.public_id).first()
    db.session.delete(note)
    db.session.commit()
    return redirect(url_for('notes'))

@app.route('/delete/category', methods=["POST"])
@token_required
def deleteCategory(current_user):
    formCategory = request.form['multiple']
    oneCategory = Category.query.filter_by(name=current_user.public_id, category=formCategory).first()
    db.session.delete(oneCategory)
    db.session.commit()
    return redirect(url_for('notes'))

@app.route('/edit/category', methods=["POST"])
@token_required
def editCategory(current_user):
    formCategory = request.form['multiple']
    newName = request.form['newCategoryName']
    oneCategory = Category.query.filter_by(name=current_user.public_id, category=formCategory).first()
    oneCategory.category = newName
    db.session.commit()
    return redirect(url_for('notes'))


@app.route('/notes/edit/<id>', methods=["POST"])
@token_required
def editNote(current_user, id):
    text = request.form['text']
    label = request.form['label']

    note = Notes.query.filter_by(id=id, public_id=current_user.public_id).first()
    note.text = text
    note.label = label
    db.session.commit()
    return redirect(f'/notes/{note.category}/{id}')



with app.app_context():
    db.create_all()
    db.session.commit()

if __name__ == "__main__":
    app.run(debug=True)
