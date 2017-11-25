# -*- coding: utf-8 -*-

'''
@author: Kevin He

Description: Extract recipe data from food2fork API, process the raw data, store it in a database file
'''

from string import digits
from string import maketrans
import sqlite3
import re
import urllib2
import json

def get_recipe_data(recipe_search, conn, header):

    for r in range(len(recipe_search)):  

        #Search for the recipes, save the recipe id and recipe title 	**GET API KEY FROM FOOD2FORK. ITS FREE
        url_search = "http://food2fork.com/api/search?key=YOUR_KEY&q=" + recipe_search[r]
        response = urllib2.urlopen(urllib2.Request(url_search,headers=header))
        data = json.loads(response.read())

        title = [result['title'] for result in data['recipes']]
        recipe_id = [result['recipe_id'] for result in data['recipes']]

        #Make sure there are no duplicate recipes
        cursor = conn.execute("SELECT recipe_title from RECIPE")
        for row in cursor:
            existing_title = str(row).replace("(u'", "").replace("',)", "").replace('(u"', '').replace('",)', '')
            if existing_title in title:
                index = title.index(existing_title)
                title.remove(title[index])
                recipe_id.remove(recipe_id[index])

        #Extract the recipe information using the recipe id
        for y in range(len(recipe_id)):
            if y==10:    #Only take ten results per recipe_search item for now
                break

            url_get = "http://food2fork.com/api/get?key=YOUR_KEY&rId=" + recipe_id[y] #must use recipe ID to search
            response_2 = urllib2.urlopen(urllib2.Request(url_get,headers=header))
            data_2 = json.loads(response_2.read())

            ingredients = ' + '.join(data_2['recipe']['ingredients'])
            ingredients = re.sub(u'\xbd', '1/2', ingredients) 
            ingredients = re.sub(u"(\u2018|\u2019)", "'", ingredients)
            ingredients = re.sub(u'\xbc', '1/4', ingredients) 

            image_url = data_2['recipe']['image_url']
            only_ing = get_only_ingredient(str(ingredients).split(" + "))
                
            #input data into databse
            conn.execute("INSERT INTO RECIPE (recipe_id, recipe_title, recipe_ingredient, recipe_image_url,only_ingredient) VALUES (?,?,?,?,?)", (recipe_search[r] + str(y), title[y],ingredients,image_url,only_ing));

    conn.commit()    

def process_data(ing_list):

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

    for ingr in ing_list:
        ing = ingr.lower()
        
        #Skip if line starts with 'For the Salad', 'Sauce:', 'Dressing:', etc
        if (ing.find("for the ") == 0) or (ing.find(":") == len(ing)):
            continue

        if "xf1" in ing:
            ing = re.sub("xf1", "n", ing)            #Replace ñ (xf1) with n
        if "&frac" in ing:
            num = ing[ing.find("&frac")+5]
            den = ing[ing.find("&frac")+6]           #Remove &frac (&frac12 = 1/2)
            fraction = num + "/" + den
            ing = re.sub("&frac" + num + den, " " + fraction + " ", ing)
        if "&#8532" in ing:
            ing = re.sub("&#8532", " 2/3 ", ing)    #Remove &nbsp (&#8532 = " 2/3")
        if "&nbsp" in ing:
            ing = re.sub("&nbsp", "", ing)          #Remove &nbsp (&nbsp = " ")
        
        ing = ing.strip("-").strip()                #Remove extra spacing and hyphen in front/back of ing. Strip spacing after!!
        ing = " " + ing + " " + " "                 #Add spacing at end for convenience & consistency
        ing = re.sub("[\(\[].*?[\)\]]", "", ing)    #Remove words inside () [] brackets

        #Remove words that come before a colon :
        if ': ' in ing:
            ing = " " + ing.split(': ', 1)[1]    
        #Remove words that come after a period . A character must come before the period (Exception: oz. lb.)                    
        if '. ' in ing and ing[ing.find(". ")-1] != ' ':    
            if (ing[ing.find(". ")-1] != 'z' and ing[ing.find(". ")-2] != 'o'):
                if (ing[ing.find(". ")-1] != 'b' and ing[ing.find(". ")-2] != 'l'):
                    ing = ing.split('. ', 1)[0]    + " " + " "        
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
                if ing[(ing.find(s) - 1)] == "-":               #e.g. 2-ounces
                    ing = re.sub('-' + s + ' ', ' ', ing)       #Remove amount words WITH HYPHEN AT BACK -
                elif ing[(ing.find(s) + len(s))] == ",":        #e.g. 2 ounces, weight
                    ing = re.sub(' ' + s + ',' + ' ', ' ', ing) #Remove amount words WITH COMMA IN FRONT,
                elif ing[(ing.find(s) + len(s))] == ".":        #e.g. 2 ounces, weight
                    ing = re.sub(' ' + s + '.' + ' ', ' ', ing) #Remove amount words WITH PERIOD IN FRONT,
                else:
                    ing = re.sub(' ' + s + ' ', ' ', ing)       #Remove amount words

        #Remove any words in the word_desc list
        if any(x in ing for x in word_desc):
            wd = (t for t in word_desc if t in ing) 
            for t in wd:
                if ing[(ing.find(t) - 1)] == " ":        #For efficiency
                    if ing[(ing.find(t) + len(t))] != " ":        #if end of ing is not a space
                        if ing[(ing.find(t) + len(t))] == "d":
                            if ing[(ing.find(t) + len(t) + 1)] == " ":          #e.g. slice'd'
                                ing = re.sub(' ' + t + 'd ', ' ', ing)          #Remove desc words WITH D IN FRONT
                            elif ing[(ing.find(t) + len(t) + 1)] == ",":        #e.g. slice'd,'
                                ing = re.sub(' ' + t + 'd, ', ' ', ing)         #Remove desc words WITH S IN FRONT and a COMMA next
                        elif ing[(ing.find(t) + len(t))] == "s":
                            if ing[(ing.find(t) + len(t) + 1)] == " ":          #e.g. clove's'
                                ing = re.sub(' ' + t + 's' + ' ', ' ', ing)     #Remove desc words WITH S IN FRONT
                            elif ing[(ing.find(t) + len(t) + 1)] == ",":        #e.g. clove's,'
                                ing = re.sub(' ' + t + 's, ', ' ', ing)         #Remove desc words WITH S IN FRONT and a COMMA next
                        elif ing[(ing.find(t) + len(t))] == "e":
                            if ing[(ing.find(t) + len(t) + 1)] == "s":
                                if ing[(ing.find(t) + len(t) + 2)] == " ":          #e.g. bunch'es'
                                    ing = re.sub(' ' + t + 'es ', ' ', ing)         #Remove description words WITH ES IN FRONT
                                elif ing[(ing.find(t) + len(t) + 2)] == ",":        #e.g. bunch'es,'
                                    ing = re.sub(' ' + t + 'es, ', ' ', ing)        #Remove description words WITH ES IN FRONT and a COMMA next
                            elif ing[(ing.find(t) + len(t) + 1)] == "d":
                                if ing[(ing.find(t) + len(t) + 2)] == " ":          #e.g. bunch'ed'
                                    ing = re.sub(' ' + t + 'ed ', ' ', ing)         #Remove description words WITH ED IN FRONT
                                elif ing[(ing.find(t) + len(t) + 2)] == ",":        #e.g. bunch'ed,'
                                    ing = re.sub(' ' + t + 'ed, ', ' ', ing)        #Remove description words WITH ED IN FRONT and a COMMA next
                        elif ing[(ing.find(t) + len(t))] == "l":    
                            if ing[(ing.find(t) + len(t) + 1)] == "y":
                                if ing[(ing.find(t) + len(t) + 2)] == " ":          #e.g. fresh'ly'
                                    ing = re.sub(' ' + t + 'ly ', ' ', ing)         #Remove description words WITH LY IN FRONT
                                elif ing[(ing.find(t) + len(t) + 2)] == ",":        #e.g. fresh'ly,'
                                    ing = re.sub(' ' + t + 'ly, ', ' ', ing)        #Remove description words WITH LY IN FRONT and a COMMA next
                        elif ing[(ing.find(t) + len(t))] == "i":    
                            if ing[(ing.find(t) + len(t) + 1)] == "n" and ing[(ing.find(t) + len(t) + 2)] == "g":
                                if ing[(ing.find(t) + len(t) + 3)] == " ":          #e.g. melt'ing'
                                    ing = re.sub(' ' + t + 'ing ', ' ', ing)        #Remove description words WITH ING IN FRONT
                                elif ing[(ing.find(t) + len(t) + 2)] == ",":        #e.g. melt'ing,'
                                    ing = re.sub(' ' + t + 'ing, ', ' ', ing)       #Remove description words WITH ING IN FRONT and a COMMA next
                        elif ing[(ing.find(t) + len(t))] == t[-1]:    
                            if ing[ing.find(t):(ing.find(t) + len(t)+4)] == (t + t[-1]+"ed "):      #e.g. chop'ped'
                                ing = re.sub(' ' + t + t[-1] + 'ed ', ' ', ing)                     #Remove description words WITH XED IN FRONT
                            elif ing[ing.find(t):(ing.find(t) + len(t)+5)] == (t + t[-1]+"ed, "):   #e.g. chop'ped,'
                                ing = re.sub(' ' + t + t[-1] + 'ed, ', ' ', ing)                    #Remove description words WITH XED IN FRONT and a COMMA next
                        
                        elif ing[(ing.find(t) + len(t))] == ",":                #e.g. shredded',' boneless chicken
                            ing = re.sub(' ' + t + ', ', ' ', ing)              #Remove description words WITH COMMA IN FRONT
                        elif ing[(ing.find(t) + len(t))] == "\\" and ing[(ing.find(t) + len(t) + 1)] == "n": #e.g. taste'\n'
                            ing = re.sub(' ' + t + r'\\n ', ' ', ing)           #Remove description words WITH \n IN FRONT
                        elif ing[(ing.find(t) + len(t))] == "-":
                            ing = re.sub(' ' + t + '-', ' ', ing)         #Remove description words that's a combo like good-tasting
                    else:
                        ing = re.sub(' ' + t + ' ', ' ', ing)             #Remove description words 

        #Remove words that come after a comma ,
        if ', ' in ing:
            ing = ing.split(', ', 1)[0] + " " + " "        
        #Remove //n at the end        
        if ing.endswith(r'\n' + " " + " "):
            ing = ing[:-4]                            
        ing = re.sub("[_%/,;()'*~\"+]", '', ing)    #Remove extraneous characters
        ing = ing.translate(None, digits)           #Remove digits    
        ing = ing.replace(".", "")                  #Remove period cuz re.sub is being stupid
        ing = ing.replace("\\", "")                 #Remove / from string
        ing = ing.strip().strip("-").strip()        #Remove extra spacing and hyphen in front/back of ing. Strip spacing FIRST!!

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
                ing = ing[(len(g)-1):]        #e.g. Remove 'and' if it appears in very front of ing

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
        elif ' with ' in ing:                #Split words if they have 'with', such as 'tomatoes with green chilli'
            ing = ing.split(' with ')
            for a in range(len(ing)):
                queries.append(ing[a].strip())
        elif ' or ' in ing:                  #Split words if they have 'or', such as 'curly pasta or linguini pasta'
            ing = ing.split(' or ')
            for a in range(len(ing)):
                queries.append(ing[a].strip())                     
        else:
            if ing == "":                    #If algorithm failed and gives a blank value
                print ingr
            else:
                ing = " ".join(ing.split())
                queries.append(ing.strip())

    return queries

def get_only_ingredient(ing_list):

    queries = process_data(ing_list)

    queries = " + ".join(queries)

    return queries

if __name__ == "__main__":

    #Open database connection
    conn = sqlite3.connect('recipe.db')
    #conn.execute("CREATE TABLE RECIPE (recipe_id text, recipe_title text, recipe_ingredient text, recipe_image_url text);");
    
    header={'User-Agent':"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.134 Safari/537.36"}
    recipe_search = []        #['lobster','chicken','pizza','salmon','spaghetti','omelet', 'macaroni and cheese', 'hamburger', 'curry', 'pasta', 'soup', 'stir fried rice', 'noodles', 'salad', 'sandwich']
    
    get_recipe_data(recipe_search,conn,header)
    
    conn.close()
