# -*- coding: utf-8 -*-

import sqlite3
import requests
import urllib2
import os

#Global Variables
r_id = []

#add the directory for your image here
DIR="/home/turtlebot22/Summer2017/RecipeAPI/RECIPE_PICS"
header={'User-Agent':"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.134 Safari/537.36"
}

#Connect with database
conn = sqlite3.connect('recipe.db')
image_url = conn.execute("SELECT recipe_image_url from RECIPE")
recipe_id = conn.execute("SELECT recipe_id from RECIPE")	#Use this as image names

#Save recipe_id values into python variables
for row in recipe_id:
	row = ''.join(row)	#must do ''.join(row) cuz row is tuple object and need to be converted to string
	r_id.append(row)
	
#SAVE IMAGE FILE
p = 0
for row in image_url:
	row = ''.join(row) 
	req = urllib2.Request(row, headers={'User-Agent' : header})
        raw_img = urllib2.urlopen(req).read()
	f = open(os.path.join(DIR, r_id[p]+".jpg"), 'wb')
	f.write(raw_img)
	f.close()
	p = p + 1
