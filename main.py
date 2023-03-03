import openai
import  requests, json, time, os, random, schedule
from requests.auth import HTTPBasicAuth
from mastodon import Mastodon

token = os.environ['token_mast']
openAiSecret = os.environ['openAiSecret']
org_id = os.environ['org_id']
openai.organization = org_id
openai.api_key = openAiSecret
openai.Model.list()

def getBook():
  with open("lista.txt", "r") as f:
    lista = eval(f.read())
  with open("usados.txt", "r") as f:
    usados = f.read()
  usados = usados.split("\n")
  #print(usados)
  disponibles = []
  for libro in lista:
    if libro not in usados:
      disponibles.append(libro)
  
  
  libro = random.choice(disponibles)
  with open("usados.txt", "a+") as f:
    f.write(f"\n{libro}")
  print(libro)
  return libro
def getResumen(libro):
  prompt = f"sumarice {libro} in 50 words in spanish. Sin decir el titulo ni el autor"
  request = openai.Completion.create(
        model="text-davinci-003", prompt=prompt, max_tokens=200,temperature=1)
  resumen = request["choices"][0]["text"].strip().capitalize()
  return resumen

def publicarToot():
  mastodon = Mastodon(
      access_token = token,
      api_base_url = 'https://mastodon.social'
  )
  libro = getBook()
  toot = toot=mastodon.toot(getResumen(libro))
  time.sleep(900)
  mastodon.status_post(libro , in_reply_to_id = toot)

schedule.every(2).hours.do(publicarToot)
while True:
  schedule.run_pending()
  time.sleep(1)
