import datetime

from tv_annotation.ai_client import upload_image

current = datetime.datetime.now()
screenshot = upload_image(r"E:\project\ui-auto\backend\data\replay\SQAST-24894\20260227_142726\step_1_compressed.jpg")
print(screenshot)
print(datetime.datetime.now()-current)