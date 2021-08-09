from django.db import models
from django.utils import timezone


class FormManager(models.Manager):
    def miscellaneous(self):
        return self.filter(type=self.model.FormType.MISCELLANEOUS)

    def hacker_application(self):
        return self.filter(type=self.model.FormType.HACKER_APPLICATION)

    def viewable_hacker_application(self):
        """
        Hacker application form that is viewable.
        """
        return self.hacker_application().filter(
            is_draft=False,
        )

    def open_hacker_application(self):
        """
        Hacker application form that is open to submissions.
        """
        return self.viewable_hacker_application().filter(
            start_at__lte=timezone.now(),
            end_at__gte=timezone.now(),
        )
