from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from flask import current_app

class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')

class RegistrationForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[
        DataRequired(), 
        Length(min=3, max=20, message='Имя пользователя должно быть от 3 до 20 символов')
    ])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[
        DataRequired(),
        Length(min=6, message='Пароль должен быть не менее 6 символов')
    ])
    password2 = PasswordField('Повторите пароль', validators=[
        DataRequired(), 
        EqualTo('password', message='Пароли не совпадают')
    ])
    submit = SubmitField('Зарегистрироваться')
    
    def validate_username(self, username):
        from models import User
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Это имя пользователя уже занято')
    
    def validate_email(self, email):
        from models import User
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Этот email уже используется')

class CaseGenerationForm(FlaskForm):
    level = SelectField('Уровень сложности', choices=[
        ('beginner', 'Начинающий'),
        ('intermediate', 'Средний'),
        ('advanced', 'Продвинутый')
    ], validators=[DataRequired()])
    topic = StringField('Тема (необязательно)', validators=[Length(max=100)])
    submit = SubmitField('Сгенерировать кейс')

class CaseEditForm(FlaskForm):
    title = StringField('Название', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Описание', validators=[DataRequired()])
    level = SelectField('Уровень сложности', choices=[
        ('beginner', 'Начинающий'),
        ('intermediate', 'Средний'),
        ('advanced', 'Продвинутый')
    ], validators=[DataRequired()])
    status = SelectField('Статус', choices=[
        ('new', 'Новый'),
        ('in_progress', 'В процессе'),
        ('completed', 'Завершен'),
        ('archived', 'Архив')
    ], validators=[DataRequired()])
    submit = SubmitField('Сохранить')

class ProfileEditForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[
        DataRequired(), 
        Length(min=3, max=20)
    ])
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Обновить профиль')

