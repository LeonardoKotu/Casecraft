from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Case
from forms import LoginForm, RegistrationForm, CaseGenerationForm, CaseEditForm, ProfileEditForm
from config import Config
from datetime import datetime
import requests
import json

app = Flask(__name__)
app.config.from_object(Config)

# Инициализация расширений
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Создание таблиц
with app.app_context():
    db.create_all()

# Функция для генерации кейсов через HuggingFace API
def generate_case_with_ai(level, topic=None):
    """
    Генерация кейса через HuggingFace Inference API
    """
    
    # Формирование промпта для генерации
    level_names = {
        'beginner': 'начинающего',
        'intermediate': 'среднего',
        'advanced': 'продвинутого'
    }
    
    level_name = level_names.get(level, 'начинающего')
    
    prompt = f"""Создай программистский кейс для практики уровня {level_name}.

Требования:
- Кейс должен быть практичным и интересным
- Уровень сложности: {level_name}
"""
    
    if topic:
        prompt += f"- Тема: {topic}\n"
    
    prompt += """
Формат ответа:
Название: [название кейса]
Описание: [подробное описание задачи, что нужно сделать, какие технологии использовать]"""

    # Резервные кейсы на случай ошибки API
    fallback_cases = {
        'beginner': {
            'title': 'Создание простого калькулятора',
            'description': 'Разработайте калькулятор на Python, который выполняет базовые математические операции (сложение, вычитание, умножение, деление). Добавьте обработку ошибок для деления на ноль и валидацию входных данных.'
        },
        'intermediate': {
            'title': 'Система управления задачами с базой данных',
            'description': 'Создайте веб-приложение для управления задачами с использованием Flask и SQLAlchemy. Реализуйте CRUD операции, фильтрацию по статусу, поиск и сортировку. Добавьте систему приоритетов и дедлайнов.'
        },
        'advanced': {
            'title': 'Микросервисная архитектура для обработки данных',
            'description': 'Разработайте систему из нескольких микросервисов для обработки больших объемов данных. Используйте очереди сообщений (RabbitMQ/Kafka), реализуйте асинхронную обработку, добавьте мониторинг и логирование. Обеспечьте отказоустойчивость и масштабируемость.'
        }
    }
    
    try:
        # Вызов HuggingFace API
        api_url = f"https://api-inference.huggingface.co/models/{app.config['HUGGINGFACE_MODEL']}"
        headers = {
            "Authorization": f"Bearer {app.config['HUGGINGFACE_API_TOKEN']}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 300,
                "temperature": 0.8,
                "top_p": 0.9,
                "return_full_text": False
            }
        }
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            
            # Парсинг ответа от HuggingFace
            if isinstance(result, list) and len(result) > 0:
                generated_text = result[0].get('generated_text', '')
            elif isinstance(result, dict):
                generated_text = result.get('generated_text', '')
            else:
                generated_text = str(result)
            
            # Извлечение названия и описания из сгенерированного текста
            title, description = parse_ai_response(generated_text, level)
            
            if title and description:
                return {
                    'title': title,
                    'description': description
                }
            else:
                # Если не удалось распарсить, используем fallback
                print("Не удалось распарсить ответ от API, используем fallback")
                return fallback_cases.get(level, fallback_cases['beginner'])
        else:
            # Ошибка API, используем fallback
            print(f"Ошибка API: {response.status_code} - {response.text}")
            return fallback_cases.get(level, fallback_cases['beginner'])
            
    except requests.exceptions.Timeout:
        print("Таймаут при запросе к API, используем fallback")
        return fallback_cases.get(level, fallback_cases['beginner'])
    except Exception as e:
        print(f"Ошибка при вызове HuggingFace API: {e}")
        return fallback_cases.get(level, fallback_cases['beginner'])

def parse_ai_response(text, level):
    """
    Парсинг ответа от AI для извлечения названия и описания
    """
    title = None
    description = None
    
    # Попытка найти "Название:" и "Описание:" в тексте
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith('Название:') or line.startswith('название:'):
            title = line.split(':', 1)[1].strip()
        elif line.startswith('Описание:') or line.startswith('описание:'):
            description = line.split(':', 1)[1].strip()
            # Если описание продолжается на следующих строках
            if i + 1 < len(lines):
                remaining_lines = [l.strip() for l in lines[i+1:] if l.strip() and not l.strip().startswith('Название:')]
                if remaining_lines:
                    description += ' ' + ' '.join(remaining_lines)
    
    # Если не нашли структурированный ответ, пытаемся извлечь из текста
    if not title or not description:
        # Берем первую строку как название
        first_line = lines[0].strip() if lines else ""
        if first_line and len(first_line) < 100:
            title = first_line
        else:
            title = f"Кейс уровня {level}"
        
        # Остальное как описание
        if len(lines) > 1:
            description = ' '.join([l.strip() for l in lines[1:] if l.strip()])
        else:
            description = text.strip()
    
    # Если описание слишком короткое, дополняем
    if not description or len(description) < 50:
        description = text.strip() if text.strip() else f"Практический кейс для программистов уровня {level}"
    
    # Ограничиваем длину
    if len(title) > 200:
        title = title[:197] + "..."
    if len(description) > 2000:
        description = description[:1997] + "..."
    
    return title, description

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        flash('Неверное имя пользователя или пароль', 'error')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы успешно вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    form = CaseGenerationForm()
    
    # Статистика пользователя
    total_cases = Case.query.filter_by(user_id=current_user.id).count()
    completed_cases = Case.query.filter_by(user_id=current_user.id, status='completed').count()
    in_progress_cases = Case.query.filter_by(user_id=current_user.id, status='in_progress').count()
    
    stats = {
        'total': total_cases,
        'completed': completed_cases,
        'in_progress': in_progress_cases,
        'new': Case.query.filter_by(user_id=current_user.id, status='new').count()
    }
    
    return render_template('dashboard.html', form=form, stats=stats)

@app.route('/generate_case', methods=['POST'])
@login_required
def generate_case():
    form = CaseGenerationForm()
    if form.validate_on_submit():
        # Генерация кейса через AI
        ai_response = generate_case_with_ai(
            level=form.level.data,
            topic=form.topic.data if form.topic.data else None
        )
        
        # Создание кейса в базе данных
        case = Case(
            title=ai_response['title'],
            description=ai_response['description'],
            level=form.level.data,
            status='new',
            user_id=current_user.id
        )
        db.session.add(case)
        db.session.commit()
        
        flash('Кейс успешно сгенерирован!', 'success')
        return redirect(url_for('my_cases'))
    
    flash('Ошибка при генерации кейса', 'error')
    return redirect(url_for('dashboard'))

@app.route('/my_cases')
@login_required
def my_cases():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    level_filter = request.args.get('level', 'all')
    
    query = Case.query.filter_by(user_id=current_user.id)
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    if level_filter != 'all':
        query = query.filter_by(level=level_filter)
    
    cases = query.order_by(Case.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    # Статистика
    stats = {
        'total': Case.query.filter_by(user_id=current_user.id).count(),
        'by_status': {
            'new': Case.query.filter_by(user_id=current_user.id, status='new').count(),
            'in_progress': Case.query.filter_by(user_id=current_user.id, status='in_progress').count(),
            'completed': Case.query.filter_by(user_id=current_user.id, status='completed').count(),
            'archived': Case.query.filter_by(user_id=current_user.id, status='archived').count()
        },
        'by_level': {
            'beginner': Case.query.filter_by(user_id=current_user.id, level='beginner').count(),
            'intermediate': Case.query.filter_by(user_id=current_user.id, level='intermediate').count(),
            'advanced': Case.query.filter_by(user_id=current_user.id, level='advanced').count()
        }
    }
    
    return render_template('my_cases.html', cases=cases, stats=stats, 
                         status_filter=status_filter, level_filter=level_filter)

@app.route('/case/<int:case_id>')
@login_required
def view_case(case_id):
    case = Case.query.get_or_404(case_id)
    if case.user_id != current_user.id:
        flash('У вас нет доступа к этому кейсу', 'error')
        return redirect(url_for('my_cases'))
    
    form = CaseEditForm(obj=case)
    return render_template('case_detail.html', case=case, form=form)

@app.route('/case/<int:case_id>/edit', methods=['POST'])
@login_required
def edit_case(case_id):
    case = Case.query.get_or_404(case_id)
    if case.user_id != current_user.id:
        flash('У вас нет доступа к этому кейсу', 'error')
        return redirect(url_for('my_cases'))
    
    form = CaseEditForm()
    if form.validate_on_submit():
        case.title = form.title.data
        case.description = form.description.data
        case.level = form.level.data
        case.status = form.status.data
        case.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Кейс успешно обновлен!', 'success')
        return redirect(url_for('view_case', case_id=case.id))
    
    return render_template('case_detail.html', case=case, form=form)

@app.route('/case/<int:case_id>/delete', methods=['POST'])
@login_required
def delete_case(case_id):
    case = Case.query.get_or_404(case_id)
    if case.user_id != current_user.id:
        flash('У вас нет доступа к этому кейсу', 'error')
        return redirect(url_for('my_cases'))
    
    db.session.delete(case)
    db.session.commit()
    flash('Кейс успешно удален', 'success')
    return redirect(url_for('my_cases'))

@app.route('/profile')
@login_required
def profile():
    form = ProfileEditForm(obj=current_user)
    
    # Статистика пользователя
    user_stats = {
        'total_cases': Case.query.filter_by(user_id=current_user.id).count(),
        'completed_cases': Case.query.filter_by(user_id=current_user.id, status='completed').count(),
        'member_since': current_user.created_at.strftime('%d.%m.%Y')
    }
    
    return render_template('profile.html', form=form, stats=user_stats)

@app.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    form = ProfileEditForm()
    if form.validate_on_submit():
        # Проверка уникальности username и email
        if form.username.data != current_user.username:
            if User.query.filter_by(username=form.username.data).first():
                flash('Это имя пользователя уже занято', 'error')
                return redirect(url_for('profile'))
        
        if form.email.data != current_user.email:
            if User.query.filter_by(email=form.email.data).first():
                flash('Этот email уже используется', 'error')
                return redirect(url_for('profile'))
        
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Профиль успешно обновлен!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('profile.html', form=form)

if __name__ == '__main__':
    app.run(debug=True)

