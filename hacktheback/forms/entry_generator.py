import random
import datetime

from hacktheback.forms.models import *

users = FormResponse.objects.all()[:20]

# my app id = c82bb862-aaf4-4b8a-8091-e22483cb4696
# my id = 5803ff4c-0a22-4de4-88cf-85988e776743


meal_types = HackerFoodTracking.Meal.choices
for i in range(20):
    food = HackerFoodTracking()
    food.application = users[i]
        
    food.meal = random.choice(meal_types)[0]
    food.save()

f1 = Food()
f1.name = "lunch"
f1.day = 1
f1.end_time = datetime.datetime.now()
f1.save()

f2 = Food()
f2.name = "dinner"
f2.day = 1
f2.end_time = datetime.datetime.now()
f2.save()

f1 = Food()
f1.name = "breakfast"
f1.day = 2
f1.end_time = datetime.datetime.now()
f1.save()

f1 = Food()
f1.name = "lunch"
f1.day = 2
f1.end_time = datetime.datetime.now()
f1.save()

f1 = Food()
f1.name = "dinner"
f1.day = 2
f1.end_time = datetime.datetime.now()
f1.save()

f1 = Food()
f1.name = "breakfast"
f1.day = 3
f1.end_time = datetime.datetime.now()
f1.save()

f1 = Food()
f1.name = "lunch"
f1.day = 3
f1.end_time = datetime.datetime.now()
f1.save()
