from dotenv import load_dotenv
import psycopg2
import os

load_dotenv()

conn = psycopg2.connect(
    dbname = os.getenv("DB_NAME"),
    user = os.getenv("DB_USER"),
    password = os.getenv("DB_PASSWORD"), 
    host = os.getenv("DB_HOST"),
    port = os.getenv("DB_PORT")
)

cursor = conn.cursor()
cursor.execute('SELECT * FROM doctors;')
for row in cursor.fetchall():
    print(row)
cursor.close()
conn.close()
