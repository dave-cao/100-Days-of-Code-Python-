from datetime import date
from functools import wraps

from flask import Flask, abort, flash, redirect, render_template, url_for
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from werkzeug.security import check_password_hash, generate_password_hash

from forms import CommentForm, CreatePostForm, LoginForm, RegisterForm

app = Flask(__name__)
app.config["SECRET_KEY"] = "8BYkEfBA6O6donzWlSihBXox7C0sKR6b"
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///blog.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# DB relationship
Base = declarative_base()

# Flask Login
login_manager = LoginManager()
login_manager.init_app(app)

# Gravatar!
gravatar = Gravatar(
    app,
    size=100,
    rating="g",
    default="retro",
    force_default=False,
    force_lower=False,
    use_ssl=False,
    base_url=None,
)

# Create admin-only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        # Otherwise continue with the route function
        return f(*args, **kwargs)

    return decorated_function


@login_manager.user_loader
def load_user(id):
    return User.query.get(id)


##CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author = relationship("User", back_populates="posts")
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # Blog to comments -- one to many
    comments = relationship("Comment", back_populates="post")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))

    # User to blog posts -- one to many
    posts = relationship("BlogPost", back_populates="author")

    # user to comments -- one to many
    comments = relationship("Comment", back_populates="author")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    # Comments to Uesrs -- many to one
    author = relationship("User", back_populates="comments")
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Comments to blog -- many to one
    post = relationship("BlogPost", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))


@app.route("/")
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()

    # if form is submitted
    if form.validate_on_submit():

        # user information
        email = form.email.data

        #  If user exists already
        user = User.query.filter_by(email=email).first()
        if user:
            flash("Email already exists! Please login instead.")
            return redirect(url_for("login"))

        # If user doesn't exist then create user
        password = generate_password_hash(
            form.password.data, method="pbkdf2:sha256", salt_length=8
        )
        new_user = User(email=email, password=password, name=form.name.data)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        # if user exists, than check hashed password
        if not user:
            flash("This email doesn't exist in our database!")
            return render_template("login.html")

        # check hashed password
        if check_password_hash(pwhash=user.password, password=form.password.data):
            login_user(user)
            return redirect(url_for("get_all_posts"))
        else:
            # password is incorrect
            flash("Incorrect password, try again!")
            return render_template("login.html")

    return render_template("login.html", form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("get_all_posts"))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    all_comments = db.session.query(Comment).all()
    requested_post = BlogPost.query.get(post_id)
    form = CommentForm()
    if form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
                text=form.body.data,
                author=current_user,
                author_id=current_user.id,
                post=requested_post,
                post_id=post_id,
            )
            db.session.add(new_comment)
            db.session.commit()
            all_comments = db.session.query(Comment).all()

        else:
            flash("You need to be logged in to make a comment!")
            return redirect(url_for("login"))

    return render_template(
        "post.html", post=requested_post, form=form, all_comments=all_comments
    )


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y"),
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body,
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for("get_all_posts"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
