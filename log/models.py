import datetime

from django.contrib.auth.models import User
from django.db import models
from django.middleware.common import _is_ignorable_404


class RequestLogManager(models.Manager):
    def create_log(self, request, url=None):
        if request.user and request.session:
            stamp = datetime.datetime.now()
            if url is None:
                url = request.get_full_path()
            if _is_ignorable_404(url):
                return None
            # Truncate in case it doesn't fit
            url = url[:self.model._meta.get_field_by_name('url')[0].max_length]
            log = self.model(user=request.user,
                             session=request.session.session_key,
                             url=url,
                             stamp=stamp)
            log.save()
            return log
        else:
            return None


class RequestLog(models.Model):
    user = models.ForeignKey(User)
    session = models.CharField(max_length=40)
    url = models.CharField(max_length=500)
    stamp = models.DateTimeField(null=True)
    objects = RequestLogManager()

    class Meta:
        unique_together = (('user', 'session', 'url', 'stamp'),)


class LogManager(models.Manager):
    """Log manager to create log records"""
    def create_log(self, varname, request, value='', stamp=None):
        if varname.startswith('E'):
            # E just signifies we can remove these for the product version
            varname = varname[1:]  # strip off the starting E
        if not stamp:
            stamp = datetime.datetime.now()
        log = self.model(user=request.user,
                         session=request.session.session_key,
                         varname=varname,
                         value=value,
                         stamp=stamp)
        log.save()
        return log


class Log(models.Model):
    user = models.ForeignKey(User, null=True)
    session = models.CharField(max_length=40)
    varname = models.CharField(max_length=30, db_index=True)
    stamp = models.DateTimeField(null=True)
    value = models.TextField(blank=True)
    objects = LogManager()

    class Meta:
        unique_together = (('user', 'session', 'varname', 'stamp'),)

    @classmethod
    def get_log_value(cls, user, varname):
        """
        Get most recent log value with given varname.
        """
        logs = Log.objects.filter(
            user=user, varname=varname).order_by('-stamp')
        return logs.exists() and logs[0].value or None

    @classmethod
    def has_varname(cls, user, varname):
        """
        Checks to see if a given varname has been logged for this user.
        """
        logs = cls.objects.filter(user=user, varname=varname)
        return logs.exists()


# Login/Logout signals
from django.contrib.auth.signals import user_logged_in, user_logged_out


def login_handler(sender, user, request, **kwargs):
    if not hasattr(request, 'user'):
        request.user = user
    Log.objects.create_log('progstar', request)
    Log.objects.create_log('VisitNo', request)
    Log.objects.create_log(
        'IPAddr', request, request.META.get('REMOTE_ADDR', ''))
    Log.objects.create_log(
        'UsrAgnt', request, request.META.get('HTTP_USER_AGENT', ''))
user_logged_in.connect(login_handler)


def logout_handler(sender, request, **kwargs):
    if request.user.is_authenticated():
        Log.objects.create_log('progstop', request)
user_logged_out.connect(logout_handler)
