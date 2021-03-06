from datetime import date,timedelta

from django.db import models
from django.utils import timezone
from stdimage import StdImageField

from mig_main.default_values import get_current_term
from requirements.models import Requirement

# Create your models here.

class GoogleCalendar(models.Model):
    name = models.CharField(max_length = 40)
    calendar_id = models.CharField(max_length=100)
    def __unicode__(self):
        return self.name

class CalendarEvent(models.Model):
    name            = models.CharField('Event Name',max_length=50)
    description     = models.TextField('Event Description')
    leaders         = models.ManyToManyField('mig_main.MemberProfile',
                                             related_name ="event_leader")
    event_type      = models.ForeignKey('requirements.EventCategory')
    assoc_officer   = models.ForeignKey('mig_main.OfficerPosition')
    announce_text   = models.TextField('Announcement Text')
    announce_start  = models.DateField('Date to start including in announcements',
                                        default=date.today)
    completed       = models.BooleanField('Event and report completed?',default=False)
    google_cal      = models.ForeignKey(GoogleCalendar)
    project_report  = models.ForeignKey('history.ProjectReport',null=True,blank=True,
                                        on_delete = models.SET_NULL)
    term            = models.ForeignKey('mig_main.AcademicTerm', default=get_current_term)    
    members_only    = models.BooleanField(default=True)
    needs_carpool   = models.BooleanField(default=False)
    use_sign_in     = models.BooleanField(default=False)
    allow_advance_sign_up = models.BooleanField(default=True)
    needs_facebook_event = models.BooleanField(default=False)
    def __unicode__(self):
        return self.name
    def get_relevant_event_type(self,status,standing):
        requirements = Requirement.objects.filter(distinction_type__status_type__name=status,distinction_type__standing_type__name=standing,term=self.term.semester_type)
        event_category=self.event_type
        while(not requirements.filter(event_category=event_category).exists() and  event_category.parent_category):
            event_category=event_category.parent_category
        return event_category

    def get_relevant_active_event_type(self):
        return self.get_relevant_event_type('Active','Undergraduate')

    def get_relevant_ugrad_electee_event_type(self):
        return self.get_relevant_event_type('Electee','Undergraduate')

    def get_relevant_grad_electee_event_type(self):
        return self.get_relevant_event_type('Electee','Graduate')

    def is_event_type(self,type_name):
        is_event_type = self.event_type.name == type_name
        event_category = self.event_type
        while (not is_event_type and event_category.parent_category !=None):
            event_category = event_category.parent_category
            is_event_type = is_event_type or event_category.name ==type_name
        return is_event_type

    def is_meeting(self):
        return self.is_event_type('Meeting Attendance')
    def is_fixed_progress(self):
        if self.is_meeting():
            return True
        if self.is_event_type('Social Credits'):
            return True
        return False
    def get_locations(self):
        locations = []
        for shift in self.eventshift_set.all():
            if shift.location in locations:
                continue
            locations.append(shift.location)
        return locations
    def get_start_and_end(self):
        output = {"start":None,'end':None}
        for shift in self.eventshift_set.all():
            if not output["start"]:
                output["start"] = shift.start_time
            elif output["start"]> shift.start_time:
                output["start"]=shift.start_time
            if not output["end"] or output["end"]< shift.end_time:
                output["end"]=shift.end_time
        return output

    def get_attendees_with_progress(self):
        return list(set([pr.member for pr in self.progressitem_set.all()]))

    

class EventShift(models.Model):
    event = models.ForeignKey(CalendarEvent)
    start_time      = models.DateTimeField()
    end_time        = models.DateTimeField()
    location        = models.CharField(max_length=100,blank=True,null=True)
    on_campus       = models.BooleanField(default=False)
    google_event_id = models.CharField('ID for gcal event',max_length=64)       
    max_attendance  = models.IntegerField(null=True,blank=True,default=None)
    drivers         = models.ManyToManyField('mig_main.UserProfile',
                                             related_name ="event_driver",
                                             blank=True, null=True,default=None)
    attendees       = models.ManyToManyField('mig_main.UserProfile',
                                             related_name ="event_attendee", 
                                             blank=True, null=True,default=None)

    def __unicode__(self):
        return self.event.name +' shift from '+str(self.start_time)+'--'+str(self.end_time)

    def is_full(self):
        if self.max_attendance is None:
            return False
        if self.attendees.count() >= self.max_attendance:
            return True
        return False

    def is_now(self):
        now=timezone.now()
        before_grace = timedelta(minutes=-30)
        after_grace = timedelta(hours=1)
        if now> (self.start_time+before_grace):
            if now < (self.end_time+after_grace):
                return True
        return False
    def is_before_start(self):
        now = timezone.now()
        if now > self.start_time:
            return False
        return True
    def can_sign_in(self):
        if self.event.use_sign_in and not self.is_full() and self.is_now():
            return True
        return False
    def can_sign_up(self):
        if self.event.allow_advance_sign_up and not self.is_full() and self.is_before_start():
            return True
        return False

class MeetingSignIn(models.Model):
    event = models.ForeignKey(CalendarEvent)
    code_phrase = models.CharField(max_length=100)
    quick_question = models.TextField()


class MeetingSignInUserData(models.Model):
    meeting_data = models.ForeignKey(MeetingSignIn)
    question_response = models.TextField()
    free_response = models.TextField()

class AnnouncementBlurb(models.Model):
    start_date = models.DateField()
    end_date = models.DateField()
    title = models.CharField(max_length = 150)
    text = models.TextField()
    contacts = models.ManyToManyField('mig_main.UserProfile')
    sign_up_link = models.CharField(max_length = 128,blank=True,null=True)
    def __unicode__(self):
        return self.title

class EventPhoto(models.Model):
    event = models.ForeignKey(CalendarEvent,blank=True,null=True)
    project_report = models.ForeignKey('history.ProjectReport',blank=True,null=True)
    caption = models.TextField(blank=True,null=True)
    photo   = StdImageField(upload_to='event_photos',thumbnail_size=(800,800))

class CarpoolPerson(models.Model):
    event = models.ForeignKey(CalendarEvent)
    person = models.ForeignKey('mig_main.UserProfile')
    ROLES_CHOICES = (
            ('DR','Driver'),
            ('RI','Rider'),
    )
    LOCATION_CHOICES = (
            ('NC','North Campus'),
            ('CC','Central Campus'),
            ('SC','South Campus'),
    )
    role = models.CharField(max_length=2,
                            choices=ROLES_CHOICES,
                            default='RI')
    location = models.CharField('Which location is closest to you?',max_length=2,
                            choices=LOCATION_CHOICES,
                            default='CC')
    number_seats = models.PositiveSmallIntegerField(null=True,blank=True)
