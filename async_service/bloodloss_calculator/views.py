import json
import random
import time
import threading
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import requests
from decouple import config
from .models import CalculationTask
import logging

logger = logging.getLogger(__name__)

MAIN_SERVICE_URL = config('MAIN_SERVICE_URL', default='http://main-service:8080')
API_KEY = config('API_KEY', default='secret_key_12345')

@csrf_exempt
@require_POST
def calculate_blood_loss(request):
    """Асинхронный расчет кровопотери"""
    try:
        data = json.loads(request.body)
        
        # Валидация данных
        required_fields = ['bloodlosscalc_id', 'operation_id', 'patient_height', 
                          'patient_weight', 'blood_loss_coeff', 'avg_blood_loss']
        
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'error': f'Missing required field: {field}'
                }, status=400)
        
        # Создаем задачу на расчет
        task = CalculationTask.objects.create(
            bloodlosscalc_id=data['bloodlosscalc_id'],
            operation_id=data['operation_id'],
            patient_height=data['patient_height'],
            patient_weight=data['patient_weight'],
            hb_before=data.get('hb_before'),
            hb_after=data.get('hb_after'),
            surgery_duration=data.get('surgery_duration'),
            blood_loss_coeff=data['blood_loss_coeff'],
            avg_blood_loss=data['avg_blood_loss'],
            status='PENDING'
        )
        
        # Запускаем расчет в отдельном потоке
        thread = threading.Thread(
            target=perform_calculation_async,
            args=(task.id, data)
        )
        thread.daemon = True
        thread.start()
        
        return JsonResponse({
            'status': 'accepted',
            'task_id': task.id,
            'message': 'Расчет кровопотери начат',
            'estimated_time': '5-10 секунд'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f'Error in calculate_blood_loss: {str(e)}')
        return JsonResponse({'error': str(e)}, status=500)

def perform_calculation_async(task_id, data):
    """Асинхронный расчет в отдельном потоке"""
    try:
        # Обновляем статус задачи
        task = CalculationTask.objects.get(id=task_id)
        task.status = 'PROCESSING'
        task.save()
        
        # Имитация задержки 5-10 секунд
        delay = random.uniform(5, 10)
        time.sleep(delay)
        
        # Выполняем расчет
        total_blood_loss = calculate_blood_loss_by_nadler(
            data['patient_height'],
            data['patient_weight'],
            data.get('hb_before'),
            data.get('hb_after'),
            data.get('surgery_duration'),
            data['blood_loss_coeff'],
            data['avg_blood_loss']
        )
        
        # Сохраняем результат
        task.total_blood_loss = total_blood_loss
        task.status = 'COMPLETED'
        task.save()
        
        # Отправляем результат в основной сервис
        send_result_to_main_service(
            bloodlosscalc_id=data['bloodlosscalc_id'],
            operation_id=data['operation_id'],
            total_blood_loss=total_blood_loss,
            task_id=task_id
        )
        
        logger.info(f'Calculation completed for task {task_id}: {total_blood_loss} ml')
        
    except Exception as e:
        logger.error(f'Error in async calculation: {str(e)}')
        # Обновляем статус при ошибке
        try:
            task = CalculationTask.objects.get(id=task_id)
            task.status = 'FAILED'
            task.error_message = str(e)
            task.save()
        except:
            pass

def calculate_blood_loss_by_nadler(height_cm, weight_kg, hb_before, hb_after, 
                                 duration_hours, blood_loss_coeff, avg_blood_loss):
    """Расчет кровопотери по формуле Надлера"""
    
    # Если есть точные данные
    if hb_before and hb_after and hb_before > hb_after and duration_hours:
        try:
            # Формула Надлера
            height_m = height_cm / 100.0
            bv = (0.3669 * (height_m ** 3) + 0.03219 * weight_kg + 0.6041) * 1000
            
            hb_drop = hb_before - hb_after
            base_blood_loss = bv * (hb_drop / hb_before)
            
            time_factor = 1.0 + (blood_loss_coeff * duration_hours)
            total_blood_loss = base_blood_loss * time_factor
            
            # Случайная вариация ±10%
            variation = random.uniform(0.9, 1.1)
            result = int(total_blood_loss * variation)
            
            # Ограничиваем разумными пределами
            return max(50, min(result, avg_blood_loss * 3))
            
        except Exception as e:
            logger.warning(f'Precise calculation failed: {e}')
    
    # Если точный расчет невозможен, используем средний с коэффициентом
    # и добавляем случайность для имитации разных пациентов
    base_result = avg_blood_loss * blood_loss_coeff
    variation = random.uniform(0.7, 1.3)  # ±30%
    
    result = int(base_result * variation)
    
    # Корректируем результат на основе роста/веса
    bmi = weight_kg / ((height_cm/100) ** 2)
    if bmi > 30:  # Ожирение
        result = int(result * 1.2)
    elif bmi < 18.5:  # Недовес
        result = int(result * 0.8)
    
    return max(50, min(result, avg_blood_loss * 2))

def send_result_to_main_service(bloodlosscalc_id, operation_id, total_blood_loss, task_id):
    """Отправка результата в основной сервис"""
    try:
        payload = {
            'bloodlosscalc_id': bloodlosscalc_id,
            'operation_id': operation_id,
            'total_blood_loss': total_blood_loss,
            'api_key': API_KEY
        }
        
        response = requests.post(
            f'{MAIN_SERVICE_URL}/api/v1/update-calculation-result',
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        
        logger.info(f'Result sent to main service: {payload}')
        
    except requests.exceptions.RequestException as e:
        logger.error(f'Failed to send result to main service: {str(e)}')
        # Можно добавить механизм повторных попыток
        retry_sending(payload)
    except Exception as e:
        logger.error(f'Unexpected error sending result: {str(e)}')

def retry_sending(payload, max_retries=3):
    """Повторная отправка при неудаче"""
    for attempt in range(max_retries):
        try:
            time.sleep(2 ** attempt)  # Экспоненциальная задержка
            
            response = requests.post(
                f'{MAIN_SERVICE_URL}/api/v1/update-calculation-result',
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            
            logger.info(f'Retry {attempt + 1} successful')
            return
            
        except requests.exceptions.RequestException:
            if attempt == max_retries - 1:
                logger.error(f'All retries failed for payload: {payload}')

@csrf_exempt
@require_POST
def direct_update(request):
    """Прямое обновление результата (для тестирования)"""
    try:
        data = json.loads(request.body)
        
        # Проверка API ключа
        if data.get('api_key') != API_KEY:
            return JsonResponse({'error': 'Invalid API key'}, status=401)
        
        # Отправляем в основной сервис
        response = requests.post(
            f'{MAIN_SERVICE_URL}/api/v1/update-calculation-result',
            json=data,
            timeout=10
        )
        
        return JsonResponse(response.json(), status=response.status_code)
        
    except Exception as e:
        logger.error(f'Error in direct_update: {str(e)}')
        return JsonResponse({'error': str(e)}, status=500)

def health_check(request):
    """Проверка здоровья сервиса"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'async-bloodloss-calculator',
        'port': 8000
    })

def task_status(request, task_id):
    """Получение статуса задачи"""
    try:
        task = CalculationTask.objects.get(id=task_id)
        
        response_data = {
            'task_id': task.id,
            'status': task.status,
            'bloodlosscalc_id': task.bloodlosscalc_id,
            'operation_id': task.operation_id,
            'created_at': task.created_at.isoformat() if task.created_at else None
        }
        
        if task.status == 'COMPLETED':
            response_data['total_blood_loss'] = task.total_blood_loss
            response_data['completed_at'] = task.completed_at.isoformat() if task.completed_at else None
        elif task.status == 'FAILED':
            response_data['error_message'] = task.error_message
        
        return JsonResponse(response_data)
        
    except CalculationTask.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)