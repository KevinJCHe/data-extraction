# -*- coding: utf-8 -*-

'''
@author: Kevin He

Description: Extracts nutrition data from USDA Food Composition Databases using NDB API. Process the raw data 
				and store it into databse file.

Nutrient identification numbers:

Calorie (kcal) - Energy:								208		
Total Fat - Total lipid (fat) : 						204
Saturated Fat - Fatty acids, total saturated: 			606
Cholestrol - Cholestrol: 								601 
Sodium - Sodium, Na: 									307
Total CarboHydrate - Carbohydrate, by difference: 		205
Dietary Fibre - Fiber, total dietary: 					291
Sugar - Sugars, total:									269
Protein - Protein										203
Vitamin A - Vitamin A, IU (International Units): 		318
Vitamin C - Vitamin C, total ascorbic acids:			401
Calcium - Calcium, Ca:									301
Iron - Iron, Fe:										303
'''

from string import digits
from string import maketrans
import sqlite3
import re
import urllib2
import json
from bs4 import BeautifulSoup
import time
import requests

#Global Variables for retrieving nutrition data
header={'User-Agent':"Windows-RSS-Platform/2.0 (IE 11.0; Windows NT 6.1) Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.134 Safari/537.36"}
removed_queries_final =[]
rem_queries =[]
rem_ndbno = []
ndbno = []
serving_amount = []
nutrients = []
found_it = False
count = 0
index = 9000
temp_index = 9000
text_length = 9000
max_iteration = 60

def get_soup(url,header):
    return BeautifulSoup(urllib2.urlopen(urllib2.Request(url,headers=header)),'html.parser')

def process_data(cursor):

	#The variable that stores the list of 2-dimensional tuples (ingredient name, original ingredient raw data)
	queries = []

	word_amount =['lb','lbs','pound','pounds','oz','ounce','ounces','kg',
					'cm','inch',
					'ml','liters','gallon','gallons','quart','quarts','qt','can','cans','pot','pots','cup','cups',
					'tablespoon','tablespoons','tbsp','teaspoon','teaspoons','tsp']

	word_desc = ['hot','cold','warm','room temperature', 
					'large','big','medium','small','weight', 
					'round','cube','thin','thinly','halved','halves','whole',
					'cut','turn','raw','fluid','clear','regular',
					'one','envelope','pack','package','container','block','tub','bag','jar','heap','loaf','bottle','piece','portion',
					'heaping',
					'toast','smoke','roast','poach','melt',
					'stalk','sprig','stick','clove','ear','leaves','bunch','cluster','bouquet','head','knob','nub','zest',
					'scant','pinch','dash','topping','dusting','garnish','splash','slice','dice','strip','chunk','fillet',
					'chop','beaten','shred','crush','mince','torn','grate','peel','sliver','julien','crumble','pit',
					'ripe','fresh','fine','good','tasting','high','quality','leftover','inexpensive','new','year','aged','homemade',
					'plus','semi','very','plenty','few','couple','additional','optional','lot','handful','bite-size','thumb-size','extra',
					'each','of','up','to','in','if','as','into','for','from','more','the','other','your',
					'serve','needed','taste','choice','favorite','percent',
					'thinning','skinless','boneless','free-range','higher-welfare']
	
	get_rid = ["and ","ml ","or ","to ","an ","with "]

	for row in cursor:
		#store the long listing of ingredients into a list of single-item ingredient (need to convert row (tuple) to string)
		ing_list = str(row).replace("(u'", "").replace("',)", "").replace('(u"', '').replace('",)', '').split(' + ')

		for ingr in ing_list:
			ing = ingr.lower()
			
			#Skip if line starts with 'For the Salad', 'Sauce:', 'Dressing:', etc
			if (ing.find("for the ") == 0) or (ing.find(":") == len(ing)):
				continue

			if "xf1" in ing:
				ing = re.sub("xf1", "n", ing)			#Replace ñ (xf1) with n
			if "&frac" in ing:
				num = ing[ing.find("&frac")+5]
				den = ing[ing.find("&frac")+6]			#Remove &frac (&frac12 = 1/2)
				fraction = num + "/" + den
				ing = re.sub("&frac" + num + den, " " + fraction + " ", ing)
			if "&#8532" in ing:
				ing = re.sub("&#8532", " 2/3 ", ing)	#Remove &nbsp (&#8532 = " 2/3")
			if "&nbsp" in ing:
				ing = re.sub("&nbsp", "", ing)			#Remove &nbsp (&nbsp = " ")
			
			ing = ing.strip("-").strip()				#Remove extra spacing and hyphen in front/back of ing. Strip spacing after!!
			ing = " " + ing + " " + " "					#Add spacing at end for convenience & consistency
			ing = re.sub("[\(\[].*?[\)\]]", "", ing)	#Remove words inside () [] brackets

			#Remove words that come before a colon :
			if ': ' in ing:
				ing = " " + ing.split(': ', 1)[1]	
			#Remove words that come after a period . A character must come before the period (Exception: oz. lb.)					
			if '. ' in ing and ing[ing.find(". ")-1] != ' ':	
				if (ing[ing.find(". ")-1] != 'z' and ing[ing.find(". ")-2] != 'o'):
					if (ing[ing.find(". ")-1] != 'b' and ing[ing.find(". ")-2] != 'l'):
						ing = ing.split('. ', 1)[0]	+ " " + " "		
			#Remove words that come after ' from a '
			if ' from a ' in ing:
				ing = ing.split(' from a ', 1)[0] + " " + " "
			#Remove words that come after a hyphen - (Exception: 1 - 2 pounds of ...)	
			if ' - ' in ing and not ing[ing.find(" - ")-1].isdigit():
				ing = ing.split(' - ', 1)[0] + " " + " "
			
			#Remove any words in the word_amount list
			if any(x in ing for x in word_amount):	
				wa = (s for s in word_amount if s in ing) 
				for s in wa:
					if ing[(ing.find(s) - 1)] == "-":				#e.g. 2-ounces
						ing = re.sub('-' + s + ' ', ' ', ing) 		#Remove amount words WITH HYPHEN AT BACK -
					elif ing[(ing.find(s) + len(s))] == ",":		#e.g. 2 ounces, weight
						ing = re.sub(' ' + s + ',' + ' ', ' ', ing) #Remove amount words WITH COMMA IN FRONT,
					elif ing[(ing.find(s) + len(s))] == ".":		#e.g. 2 ounces, weight
						ing = re.sub(' ' + s + '.' + ' ', ' ', ing) #Remove amount words WITH PERIOD IN FRONT,
					else:
						ing = re.sub(' ' + s + ' ', ' ', ing) 		#Remove amount words

			#Remove any words in the word_desc list
			if any(x in ing for x in word_desc):
				wd = (t for t in word_desc if t in ing) 
				for t in wd:
					if ing[(ing.find(t) - 1)] == " ":		#For efficiency
						if ing[(ing.find(t) + len(t))] != " ":		#if end of ing is not a space
							if ing[(ing.find(t) + len(t))] == "d":
								if ing[(ing.find(t) + len(t) + 1)] == " ":			#e.g. slice'd'
									ing = re.sub(' ' + t + 'd ', ' ', ing) 			#Remove desc words WITH D IN FRONT
								elif ing[(ing.find(t) + len(t) + 1)] == ",":		#e.g. slice'd,'
									ing = re.sub(' ' + t + 'd, ', ' ', ing) 		#Remove desc words WITH S IN FRONT and a COMMA next
							elif ing[(ing.find(t) + len(t))] == "s":
								if ing[(ing.find(t) + len(t) + 1)] == " ":			#e.g. clove's'
									ing = re.sub(' ' + t + 's' + ' ', ' ', ing) 	#Remove desc words WITH S IN FRONT
								elif ing[(ing.find(t) + len(t) + 1)] == ",":		#e.g. clove's,'
									ing = re.sub(' ' + t + 's, ', ' ', ing) 		#Remove desc words WITH S IN FRONT and a COMMA next
							elif ing[(ing.find(t) + len(t))] == "e":
								if ing[(ing.find(t) + len(t) + 1)] == "s":
									if ing[(ing.find(t) + len(t) + 2)] == " ":			#e.g. bunch'es'
										ing = re.sub(' ' + t + 'es ', ' ', ing) 		#Remove description words WITH ES IN FRONT
									elif ing[(ing.find(t) + len(t) + 2)] == ",":		#e.g. bunch'es,'
										ing = re.sub(' ' + t + 'es, ', ' ', ing) 		#Remove description words WITH ES IN FRONT and a COMMA next
								elif ing[(ing.find(t) + len(t) + 1)] == "d":
									if ing[(ing.find(t) + len(t) + 2)] == " ":			#e.g. bunch'ed'
										ing = re.sub(' ' + t + 'ed ', ' ', ing) 		#Remove description words WITH ED IN FRONT
									elif ing[(ing.find(t) + len(t) + 2)] == ",":		#e.g. bunch'ed,'
										ing = re.sub(' ' + t + 'ed, ', ' ', ing) 		#Remove description words WITH ED IN FRONT and a COMMA next
							elif ing[(ing.find(t) + len(t))] == "l":	
								if ing[(ing.find(t) + len(t) + 1)] == "y":
									if ing[(ing.find(t) + len(t) + 2)] == " ":			#e.g. fresh'ly'
										ing = re.sub(' ' + t + 'ly ', ' ', ing) 		#Remove description words WITH LY IN FRONT
									elif ing[(ing.find(t) + len(t) + 2)] == ",":		#e.g. fresh'ly,'
										ing = re.sub(' ' + t + 'ly, ', ' ', ing) 		#Remove description words WITH LY IN FRONT and a COMMA next
							elif ing[(ing.find(t) + len(t))] == "i":	
								if ing[(ing.find(t) + len(t) + 1)] == "n" and ing[(ing.find(t) + len(t) + 2)] == "g":
									if ing[(ing.find(t) + len(t) + 3)] == " ":			#e.g. melt'ing'
										ing = re.sub(' ' + t + 'ing ', ' ', ing) 		#Remove description words WITH ING IN FRONT
									elif ing[(ing.find(t) + len(t) + 2)] == ",":		#e.g. melt'ing,'
										ing = re.sub(' ' + t + 'ing, ', ' ', ing) 		#Remove description words WITH ING IN FRONT and a COMMA next
							elif ing[(ing.find(t) + len(t))] == t[-1]:	
								if ing[ing.find(t):(ing.find(t) + len(t)+4)] == (t + t[-1]+"ed "):		#e.g. chop'ped'
									ing = re.sub(' ' + t + t[-1] + 'ed ', ' ', ing) 					#Remove description words WITH XED IN FRONT
								elif ing[ing.find(t):(ing.find(t) + len(t)+5)] == (t + t[-1]+"ed, "):	#e.g. chop'ped,'
									ing = re.sub(' ' + t + t[-1] + 'ed, ', ' ', ing) 					#Remove description words WITH XED IN FRONT and a COMMA next
							
							elif ing[(ing.find(t) + len(t))] == ",":				#e.g. shredded',' boneless chicken
								ing = re.sub(' ' + t + ', ', ' ', ing) 				#Remove description words WITH COMMA IN FRONT
							elif ing[(ing.find(t) + len(t))] == "\\" and ing[(ing.find(t) + len(t) + 1)] == "n":	#e.g. taste'\n'
								ing = re.sub(' ' + t + r'\\n ', ' ', ing) 			#Remove description words WITH \n IN FRONT
							elif ing[(ing.find(t) + len(t))] == "-":
								ing = re.sub(' ' + t + '-', ' ', ing) 			#Remove description words that's a combo like good-tasting
						else:
							ing = re.sub(' ' + t + ' ', ' ', ing) 			#Remove description words 

			#Remove words that come after a comma ,
			if ', ' in ing:
				ing = ing.split(', ', 1)[0] + " " + " "		
			#Remove //n at the end		
			if ing.endswith(r'\n' + " " + " "):
				ing = ing[:-4]							
			ing = re.sub("[_%/,;()'*~\"+]", '', ing)	#Remove extraneous characters
			ing = ing.translate(None, digits)			#Remove digits	
			ing = ing.replace(".", "")					#Remove period cuz re.sub is being stupid
			ing = ing.replace("\\", "")					#Remove / from string
			ing = ing.strip().strip("-").strip()		#Remove extra spacing and hyphen in front/back of ing. Strip spacing FIRST!!

			#Remove single characters if it appears in very front of ing
			if len(ing) > 2:
				if ing[0].isalpha() and ing[1]== " ": 	
					ing = ing[1:]
				#Remove single characters if it appears in very end of ing
				if ing[len(ing)-1].isalpha() and ing[len(ing)-2] == " ": 	
					ing = ing[:-2]

			#Remove any words in the get_rid list that appear in very front of ing
			for g in get_rid:
				if ing.find(g) == 0:								
					ing = ing[(len(g)-1):]		#e.g. Remove 'and' if it appears in very front of ing

			#Remove ' a '
			if ' a ' in ing:	
				ing = re.sub(' a ', ' ', ing) 
			#Remove ' g '
			if ' g ' in ing:	
				ing = re.sub(' g ', ' ', ing) 	
			#Split words if they have 'and', such as 'mayo and mustard and ketchup'
			if ' and ' in ing:					
				ing = ing.split(' and ')
				for a in range(len(ing)):
					queries.append((ing[a].strip(),ingr))
			elif ' with ' in ing:				#Split words if they have 'with', such as 'tomatoes with green chilli'
				ing = ing.split(' with ')
				for a in range(len(ing)):
					queries.append((ing[a].strip(),ingr))
			elif ' or ' in ing:					#Split words if they have 'or', such as 'curly pasta or linguini pasta'
				ing = ing.split(' or ')
				for a in range(len(ing)):
					queries.append((ing[a].strip(),ingr)) 					
			else:
				if ing == "":					#If algorithm failed and gives a blank value
					print ingr
				else:
					ing = " ".join(ing.split())
					queries.append((ing.strip(),ingr))

	return queries

def get_ingr_from_db():

	#Retrieve ingredients from database
	conn = sqlite3.connect('recipe.db')
	raw_data = conn.execute("SELECT recipe_ingredient from RECIPE")

	#Store the ingredient names into a list of 2 dimensional tuples
	queries = process_data(raw_data)

	#Remove duplicate ingredient names from list 	**Compares only the first element of this 2 Dimensional Tuple
	queries = dict((x[0], x) for x in queries).values()

	conn.close()
	
	#Remove duplicates already inserted in database
	conn_2 = sqlite3.connect('nutrient.db')
	cursor_2 = conn_2.execute("SELECT Ingredient_Name from NUTRIENT")
	for row in cursor_2:
		ing_item = str(row).replace("(u'", "").replace("',)", "").replace('(u"', '').replace('",)', '')
		for query in queries:
			if ing_item == query[0] or ing_item == (query[0] + "s") or ing_item == query[0][:-1]:
				queries.remove(query)

	return queries

def input_nutr_data_into_db(queries,ndbno):
	conn = sqlite3.connect('nutrient.db')
	#conn.execute("CREATE TABLE NUTRIENT (Ingredient_Name text, Actual_Searched_Item text, Ndbno_Number text, Serving_Amount text)");
			
	for n in range(len(ndbno)):
		#SQL insert the columns
		'''
		for column_name in nutrients[n][0]:
			col_name = re.sub("[/,()']", '', column_name)	#Remove extraneous characters	
			col_name = col_name.split()
			col_name = "_".join(col_name)
			conn.execute("ALTER TABLE NUTRIENT ADD COLUMN %s text" % col_name);
		'''
		#SQL insert the values
		ingredient = queries[n][0]
		actual_searched_item = ndbno[n][0]
		ndbno_num = ndbno[n][1]
		ser_amount = serving_amount[n]
		nutr_name = nutrients[n][0]
		nutr_val = nutrients[n][1]
		nutr_unit = nutrients[n][2]

		conn.execute("INSERT INTO NUTRIENT (Ingredient_Name, Actual_Searched_Item, Ndbno_Number, Serving_Amount) VALUES (?,?,?,?)", (ingredient,actual_searched_item,ndbno_num,ser_amount,));
		for a in range(len(nutrients[n][0])):
			conn.execute("UPDATE NUTRIENT SET %s = (?) WHERE Ingredient_Name = (?)" % nutr_name[a], (nutr_val[a]+nutr_unit[a], ingredient,));
		conn.commit()

	conn.close()

#Algorithm functions!
def two_word_switch_alg(soup_1,text_query):
	global count, found_it

	for a in soup_1.find_all(title="Click to view reports for this food"):	
		item_name = a.string.lower().strip()
		if item_name.find(text_query) > -1:	#Try find one in which the query text exists
			ndbno.append((item_name,ndbno_num))
			found_it = True
			print "ALGORITHM: TWO WORDS SWITCH"
			break
		if count == max_iteration:
			count = 0
			break
		ndbno_num = a.string.strip()
		count = count + 1

	return found_it

def find_raw_or_fluid_alg(soup_1,query):
	global count, found_it, temp_text_length, text_length

	for a in soup_1.find_all(title="Click to view reports for this food"):			
		item_name = a.string.lower().strip()
		item_name = re.sub(",", '', item_name)	#Remove commas
		if item_name.find(query) < 15 and ("raw" in item_name or "fluid" in item_name):	#Try find one that has the word raw or fluid and query word is near the front (broccoli, raw)
			temp_text_length = len(item_name)
			found_it = True
			if temp_text_length <= text_length:#Bascially make sure you find the shortest string
				text_length = temp_text_length
				print str(text_length) + " " + item_name
				winner_1 = item_name
				winner_2 = ndbno_num
		if count == max_iteration:
			count = 0
			break
		ndbno_num = a.string.strip()
		count = count + 1
	if found_it == True: 
		ndbno.append((winner_1,winner_2))
		print "ALGORITHM: FIND RAW OR FLUID"

	return found_it

def closest_query_word_alg(soup_1,query):
	global count, found_it, index, temp_index, temp_text_length, text_length

	for a in soup_1.find_all(title="Click to view reports for this food"):	 		
		item_name = a.string.lower().strip()
		item_name = re.sub(",", '', item_name)	#Remove commas
		if item_name.find(query) > -1:	#If you find an occurence of the query word
			temp_text_length = len(item_name)
			found_it = True
			temp_index = item_name.find(query)
			if temp_text_length <= text_length:#Bascially find the shortest string, only then you check next if statement
				text_length = temp_text_length
				print str(text_length) + " " + item_name
				if temp_index <= index and temp_index > -1:#Try find one in which query word appears the closest to index 0 
					index = temp_index
					winner_3 = item_name
					winner_4 = ndbno_num
		if count == max_iteration:
			count = 0
			text_length = 9000
			break
		ndbno_num = a.string.strip()
		count = count + 1
	if found_it == True: 
		ndbno.append((winner_3,winner_4))
		print "ALGORITHM: FIND QUERY WORD THAT APPEARS CLOSEST"

	return found_it

def every_word_appear_alg(soup_1,que_words):
	global count, found_it, temp_text_length, text_length

	for a in soup_1.find_all(title="Click to view reports for this food"):	
		item_name = a.string.lower().strip()
		item_name = re.sub(",", '', item_name)	#Remove commas
		if all(q in item_name for q in que_words):	#Try find one in which all the split up query words appears somewhere
			temp_text_length = len(item_name)
			found_it = True
			if temp_text_length <= text_length:	#Bascially make sure you find the shortest string
				text_length = temp_text_length
				print str(text_length) + " " + item_name
				winner_5 = item_name
				winner_6 = ndbno_num
		if count == max_iteration:
			count = 0
			break
		ndbno_num = a.string.strip()
		count = count + 1
	if found_it == True: 
		ndbno.append((winner_5,winner_6))
		print "ALGORITHM: FIND QUERY WORD THAT ALL APPEARS"

	return found_it

def any_word_appear_alg(soup_1,que_words):
	global count, found_it, temp_text_length, text_length

	for a in soup_1.find_all(title="Click to view reports for this food"):	
		item_name = a.string.lower().strip()
		item_name = re.sub(",", '', item_name)	#Remove commas
		if any(q in item_name for q in que_words):	#Try find one in which any the split up query words appears somewhere
			temp_text_length = len(item_name)
			found_it = True
			if temp_text_length <= text_length:	#Bascially make sure you find the shortest string
				text_length = temp_text_length
				print str(text_length) + " " + item_name
				winner_7 = item_name
				winner_8 = ndbno_num
		if count == max_iteration:
			count = 0
			break
		ndbno_num = a.string.strip()
		count = count + 1
	if found_it == True: 
		ndbno.append((winner_7,winner_8))
		print "ALGORITHM: FIND QUERY WORD THAT ANY APPEARS"

	return found_it

def extract_nutrient(queries):

	global found_it, temp_index, index, text_length

	#Stage 1 input the queries into a simple text file and make sure queries are not duplicated in text file
	file = open("Ingredient.txt", "r")
	for line in file:  
		line = line.split(':', 1)[0].strip()
		for query in queries:
			if query[0] == line:
				queries.remove(query)					                                                         
	file.close()
	file = open("Ingredient.txt", "a")
	for item in queries:            
	    file.write("%s \t\t: %s\n" % (item[0],item[1]))                                                                         
	file.close()


	#Stage 1.5
	#Inputting no result query into another file
	file = open("NO RESULT.txt", "a")
	
	#Stage 2
	#GET NDBNO NUMBER USING BEAUTIFUL SOUP
	for r in range(len(queries)):
		query = queries[r][0]
		print query

		if len(query.split()) == 2:	#if query word is two words like cheddar cheese
			que_words = query.split()
			url_query = que_words[1]+"%20"+que_words[0]					#switch the words, search for cheese%cheddar
			text_query = (que_words[1] + ", "+que_words[0]).lower()		#for the actual text, search for cheese, cheddar
			url = 'https://ndb.nal.usda.gov/ndb/search/list?qlookup=' + url_query + '&ds=Standard+Reference'
			soup_1 = get_soup(url, header)
			found_it = two_word_switch_alg(soup_1,text_query)

		if found_it == False:
			url_query = '%20'.join(query.split())		#Turn onion powder to onion%powder
			url = 'https://ndb.nal.usda.gov/ndb/search/list?qlookup=' + url_query + '&ds=Standard+Reference'
			soup_1 = get_soup(url, header)
			found_it = find_raw_or_fluid_alg(soup_1,query)

			if found_it == False:
				found_it = closest_query_word_alg(soup_1,query)

				if found_it == False:
					if len(query.split()) > 1:	#if query word is more than one word
						que_words =query.split()
						found_it = every_word_appear_alg(soup_1,que_words)
						
						if found_it == False:
							found_it = any_word_appear_alg(soup_1,que_words)

							if found_it == False:
								last_word = que_words[-1]#Take the last word e.g.japanese eggplants to eggplants
								print last_word
								url_last_word = 'https://ndb.nal.usda.gov/ndb/search/list?qlookup=' + last_word + '&ds=Standard+Reference'
								soup_last_word = get_soup(url_last_word, header)
								found_it = find_raw_or_fluid_alg(soup_last_word,last_word)
								if found_it == False:
									found_it = closest_query_word_alg(soup_last_word,last_word)

									if found_it == False:
										if last_word[len(last_word) - 1] == "s":
										#if there is s at end, remove it. e.g. eggplants to eggplant
											last_word = last_word[:-1]
											print last_word
											found_it = find_raw_or_fluid_alg(soup_last_word,last_word)	#Do the find_raw_or_fluid_alg with the removed s word
											if found_it == False:
												found_it = closest_query_word_alg(soup_last_word,last_word) 	#Do the closest_query_word_alg with the removed s word

					if found_it == False:
						if len(query.split()) == 1:
							if query[len(query) -1] == "s":
							#if there is s at end, remove it.e.g. cucumbers to cucumber
								word =query[:-1]
								found_it = find_raw_or_fluid_alg(soup_1,word) 
								#Do the find_raw_or_fluid_alg with the removed s word
								if found_it == False:
									found_it = closest_query_word_alg(soup_1,word) 
									#Do the closest_query_word_alg with the removed s word

						if found_it == False:
							print "no result for " +query + " : " + url_query
							removed_queries_final.append(queries[r])

		if ndbno:			
			print ndbno[-1]
		
		#Retun global variables to default values
		found_it = False
		temp_index = 9000
		index = 9000
		text_length = 9000
		
		time.sleep(4)

	#Remove the queries that were not found
	for x in removed_queries_final:
		queries.remove(x)

	#For queries that were not found, try Branded+Food+Products instead of Standard+Reference on the url
	for r in range(len(removed_queries_final)):
		query = removed_queries_final[r][0]
		print query + " : BRANDED FOOD PRODUCT!!"

		if len(query.split()) == 2:	#if query word is two words like cheddar cheese
			que_words = query.split()
			url_query = que_words[1]+"%20"+que_words[0]			#switch the words, search for cheese%cheddar
			text_query = (que_words[1] + ", "+que_words[0]).lower()		#for the actual text, search for cheese, cheddar
			url = 'https://ndb.nal.usda.gov/ndb/search/list?qlookup=' + url_query + '&ds=Branded+Food+Products'
			soup_1 = get_soup(url, header)
			found_it = two_word_switch_alg(soup_1,text_query)

		if found_it == False:
			url_query = '%20'.join(query.split())		#Turn onion powder to onion%powder
			url = 'https://ndb.nal.usda.gov/ndb/search/list?qlookup=' + url_query + '&ds=Branded+Food+Products'
			soup_1 = get_soup(url, header)
			found_it = find_raw_or_fluid_alg(soup_1,query)

			if found_it == False:
				found_it = closest_query_word_alg(soup_1,query)

				if found_it == False:
					if len(query.split()) > 1:	#if query word is more than one word
						que_words = query.split()
						found_it = every_word_appear_alg(soup_1,que_words)
						
						if found_it == False:
							found_it = any_word_appear_alg(soup_1,que_words)

							if found_it == False:
								last_word = que_words[-1] #Take the last word e.g. japanese eggplants to eggplants
								print last_word
								url_last_word = 'https://ndb.nal.usda.gov/ndb/search/list?qlookup=' + last_word + '&ds=Branded+Food+Products'
								soup_last_word = get_soup(url_last_word, header)
								found_it = find_raw_or_fluid_alg(soup_last_word,last_word)
								if found_it == False:
									found_it = closest_query_word_alg(soup_last_word,last_word)

									if found_it == False:
										if last_word[len(last_word) - 1] == "s":	
										#if there is s at end, remove it. e.g. eggplants to eggplant
											last_word = last_word[:-1]
											print last_word
											found_it = find_raw_or_fluid_alg(soup_last_word,last_word)	#Do the find_raw_or_fluid_alg with the removed s word
											if found_it == False:
												found_it = closest_query_word_alg(soup_last_word,last_word)	#Do the closest_query_word_alg with the removed s word

					if found_it == False:
						if len(query.split()) == 1:
							if query[len(query) -1] == "s":
							#if there is s at end, remove it. e.g. cucumbers to cucumber
								word =query[:-1]
								found_it = find_raw_or_fluid_alg(soup_1,word)	
								#Do the find_raw_or_fluid_alg with the removed s word
								if found_it == False:
									found_it = closest_query_word_alg(soup_1,word) 
									#Do the closest_query_word_alg with the removed s word

						if found_it == False:
							print "NO RESULT (FINAL!!) FOR " + query + " : " + url_query
							file.write("NO RESULT (FINAL!!) FOR %s ; %s\n" % (query,removed_queries_final[r][1]))
		if found_it ==True:
			queries.append(removed_queries_final[r])
			#append found query to the end of the list queries, so parameters match with corresponding ndbno's

		if ndbno:			
			print ndbno[-1]
		
		#Retun global variables to default values
		found_it = False
		temp_index = 9000
		index = 9000
		text_length = 9000
		
		time.sleep(4)

	#GET NUTRIENT USING API
	for n in range(len(ndbno)):
		url = "https://api.nal.usda.gov/ndb/nutrients/?format=json&api_key=YOUR_KEY \
				&nutrients=208&nutrients=204&nutrients=606&nutrients=601&nutrients=307&nutrients=205&nutrients=291 \
				&nutrients=269&nutrients=203&nutrients=318&nutrients=401&nutrients=301&nutrients=303&ndbno=" + ndbno[n][1]
		response = urllib2.urlopen(url)
		data = json.loads(response.read())

		if not data['report']['foods']:	#Sometime there is no data provided
			rem_queries.append(queries[n])
			rem_ndbno.append(ndbno[n])
			print "NO DATA PROVIDED FOR " + queries[n][0] + " : " + str(ndbno[n])
			file.write("NO DATA PROVIDED FOR %s : %s ; %s\n" % (queries[n][0],str(ndbno[n]),queries[n][1]))
			continue

		#Save key values in python variables 				**Weight is always in grams. Measure is the gram equivalent of weight in other units of measure (cup, oz, etc)
		serving_amount.append(str(data['report']['foods'][0]['weight']) + "g = " + data['report']['foods'][0]['measure'])	
		#Foods is a list. I DONT KNOW WHY BUT YOU NEED A [0] IN FRONT OF FOODS TO WORK
		nutrients_name = [nutr['nutrient'] for nutr in data['report']['foods'][0]['nutrients']] 
		#Nutrients is also a list btw, containing nutrient_name, nutrient_amount, nutrient_unit
		nutrients_value = [nutr['value'] for nutr in data['report']['foods'][0]['nutrients']]	#ALL NUTRIENT IS PER 100g BASIS!!!! WEIGHT DOES NOT MATTER!!!
		nutrients_unit = [nutr['unit'] for nutr in data['report']['foods'][0]['nutrients']]

		if nutrients_value.count("--") > 12:
			print "CORRUPT DATA MOST LIKELY FOR "  + queries[n][0] + " : " + str(ndbno[n])
			file.write("CORRUPT DATA PROVIDED FOR %s : %s ; %s\n" % (queries[n][0],str(ndbno[n]),queries[n][1]))
			rem_queries.append(queries[n])
			rem_ndbno.append(ndbno[n])
			continue

		#MUST  MODIFY NUTRIENTS NAME FOR SQL COMPATIBILITY
		for r in range(len(nutrients_name)):
			nutrients_name[r] = re.sub("[/,()']", '', nutrients_name[r])
			nutrients_name[r] = nutrients_name[r].split()
			nutrients_name[r] = "_".join(nutrients_name[r])

		nutrients.append([nutrients_name, nutrients_value, nutrients_unit])

	#Remove the queries and ndbno that were not found / was empty, cuz list index out of range errors
	for x in rem_queries:
		print x
		queries.remove(x)
	for x in rem_ndbno:
		print x
		ndbno.remove(x)

	file.close()

	#Stage 3
	#Input nutrient data into nutrient database
	input_nutr_data_into_db(queries,ndbno)
	

def update_nutrient_data(query, correct_ndbno_num):
	conn = sqlite3.connect('nutrient.db')

	#Get the JSON data
	url = "https://api.nal.usda.gov/ndb/nutrients/?format=json&api_key=YOUR_KEY \
			&nutrients=208&nutrients=204&nutrients=606&nutrients=601&nutrients=307&nutrients=205&nutrients=291 \
			&nutrients=269&nutrients=203&nutrients=318&nutrients=401&nutrients=301&nutrients=303&ndbno=" + correct_ndbno_num
	response = urllib2.urlopen(url)
	data = json.loads(response.read())

	print json.dumps(data, indent = 4, sort_keys = True)
	
	if not data['report']['foods']:	#Sometime there is no data provided
		print "NO DATA PROVIDED FOR " + query + " : " + correct_ndbno_num
		return 0

	actual_searched_item = data['report']['foods'][0]['name']	
	serving_amount = str(data['report']['foods'][0]['weight']) + "g = " + data['report']['foods'][0]['measure']	
	
	nutrients_name = [nutr['nutrient'] for nutr in data['report']['foods'][0]['nutrients']] 
	nutrients_value = [nutr['value'] for nutr in data['report']['foods'][0]['nutrients']]	#ALL NUTRIENT IS PER 100g BASIS!!!! WEIGHT DOES NOT MATTER!!!
	nutrients_unit = [nutr['unit'] for nutr in data['report']['foods'][0]['nutrients']]
	
	if nutrients_value.count("--") > 12:
		print "CORRUPT DATA MOST LIKELY FOR "  + query + " : " + correct_ndbno_num
		return 0
	
	#MUST  MODIFY NUTRIENTS NAME FOR SQL COMPATIBILITY
	for r in range(len(nutrients_name)):
		nutrients_name[r] = re.sub("[/,()']", '', nutrients_name[r])
		nutrients_name[r] = nutrients_name[r].split()
		nutrients_name[r] = "_".join(nutrients_name[r])

	#Update the database
	conn.execute("UPDATE NUTRIENT SET Actual_Searched_Item = ? WHERE Ingredient_Name = ?", (actual_searched_item, query,));
	conn.execute("UPDATE NUTRIENT SET Ndbno_Number = ? WHERE Ingredient_Name = ?", (correct_ndbno_num, query,));
	conn.execute("UPDATE NUTRIENT SET Serving_Amount = ? WHERE Ingredient_Name = ?", (serving_amount, query,));
	for a in range(len(nutrients_name)):
		conn.execute("UPDATE NUTRIENT SET %s = (?) WHERE Ingredient_Name = (?)" % nutrients_name[a], (nutrients_value[a]+nutrients_unit[a], query,));
	
	conn.commit()
	conn.close()
	
if __name__ == "__main__":
	
	#Insert Nutrient Data

	#retrieve ingredients from recipe database
	queries = get_ingr_from_db()
	
	#find the nutrients, store it into database
	extract_nutrient(queries)

	#Manual Updates of Nutrient Database
	'''
	update_nutrient_data("brown sugar", "19334")	#First Parameter = Ingredient_Name, Second Paramenter = Ndbno number that you want
	update_nutrient_data("white vinegar","45137968") 
	update_nutrient_data("white button","11260") 
	update_nutrient_data("sweet apple","09003")
	update_nutrient_data("chicken","05332")
	update_nutrient_data("natural yogurt","01295")
	update_nutrient_data("corn starch","45168375")
	''' 