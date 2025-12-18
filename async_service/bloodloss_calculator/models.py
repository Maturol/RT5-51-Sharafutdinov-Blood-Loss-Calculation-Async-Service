from django.db import models

class CalculationTask(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Ожидает расчета'),
        ('PROCESSING', 'В процессе'),
        ('COMPLETED', 'Завершено'),
        ('FAILED', 'Ошибка'),
    ]
    
    bloodlosscalc_id = models.IntegerField()
    operation_id = models.IntegerField()
    
    patient_height = models.FloatField()
    patient_weight = models.IntegerField()
    
    hb_before = models.IntegerField(null=True, blank=True)
    hb_after = models.IntegerField(null=True, blank=True)
    surgery_duration = models.FloatField(null=True, blank=True)
    
    blood_loss_coeff = models.FloatField()
    avg_blood_loss = models.IntegerField()
    
    total_blood_loss = models.IntegerField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    error_message = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['bloodlosscalc_id', 'operation_id']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Task {self.id}: {self.bloodlosscalc_id}-{self.operation_id} ({self.status})"