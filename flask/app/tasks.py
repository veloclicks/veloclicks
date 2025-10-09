from celery import shared_task

# https://flask.palletsprojects.com/en/stable/patterns/celery/
@shared_task(ignore_result=False)   
def test_task():
    return ("test_task() : Task completed successfully!")

@shared_task(ignore_result=False, name='app.tasks.my_task')   
def my_task_with_any_name():
    return ("my_task_with_any_name() : Task completed successfully!")
