from django.db import models
from django.contrib.auth.models import User



class SMSMessage(models.Model):
	sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
	recipient = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)
	message = models.TextField()
	timestamp = models.DateTimeField(auto_now_add=True)
	is_read = models.BooleanField(default=False)
	
	def __str__(self):
		return f"From {self.sender.first_name} to {self.recipient.first_name}: {self.message[:20]}..."
