from django import forms

class MessageForm(forms.Form):
    message = forms.CharField(label="Сообщение", widget=forms.Textarea)