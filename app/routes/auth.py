from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired

from app.models import User

bp = Blueprint("auth", __name__)


class LoginForm(FlaskForm):
    username = StringField("Comandante", validators=[DataRequired()])
    password = PasswordField("Clave", validators=[DataRequired()])


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.map_view"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            nxt = request.args.get("next")
            return redirect(nxt or url_for("main.map_view"))
        flash("Credenciales incorrectas.", "danger")
    return render_template("login.html", form=form)


@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
