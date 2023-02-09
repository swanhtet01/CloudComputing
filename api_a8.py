from flask import Flask
from flask_restful import Resource, Api, reqparse
import pandas as pd
import datetime
import requests
import hashlib

from flask_bcrypt import Bcrypt, generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required


app = Flask(__name__)
api = Api(app)
bcrypt = Bcrypt(app) # Set up the Bcrypt extension
jwt = JWTManager(app) # Setup the Flask-JWT-Extended extension
app.config["JWT_SECRET_KEY"] = "esade_miba_group_a8"  # Change this!


# for privacy reasons, we will encode the user's password
def hash_password(password):
        return generate_password_hash(password).decode('utf8')

class SignUp(Resource):
    
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('email', type=str, help='Missing argument email', required=True,location = 'args' )
        parser.add_argument('password', type=str, help='Missing argument password', required=True,location = 'args' )
        args = parser.parse_args()  # parse arguments to dictionary

        # read our CSV
        data = pd.read_csv('users.csv')
        
        #if the email provided is already present in the database:
        if args['email'] in list(data['email']):
            return {'status': 409, 'response': f"{args['email']} already exists."}, 409
        #if it's a new email
        else:
            # create new dataframe containing new values
            entry = pd.DataFrame({
                'email': [args['email']],
                'password': [hash_password(args['password'])]
            })
            
            # add entry to database
            data = data.append(entry, ignore_index=True)
            data.to_csv('users.csv', index=False)  # save back to CSV
            return {'status': 200, 'response': 'Successfully signed up'}, 200 # return data and 200 OK
        
api.add_resource(SignUp, '/signup', endpoint='signup')


class LogIn(Resource):
    
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('email', type=str, help='Missing argument email', required=True,location = 'args')
        parser.add_argument('password', type=str, help='Missing argument password', required=True,location = 'args')
        args = parser.parse_args()  # parse arguments to dictionary

        # read our CSV
        data = pd.read_csv('users.csv')
        
        global access_token 
        
        # if the user is trying to login with an email that is not in our database.
        if args['email'] not in list(data['email']):
            return {'status': 401, 'response': "Invalid email"}, 401
        else: 
            # look for password hash in database
            password = data.loc[data['email']==args['email'], 'password'][0]
            
            if check_password_hash(password, args['password']):
                expires = datetime.timedelta(hours=1) #creating the token and setting usage limit to 1h
                access_token = create_access_token(identity=str(data.loc[data['email']==args['email']].index[0]), expires_delta=expires)
             
                return {'status': 200, 'response': 'Successfully logged in', 'token': access_token}, 200 # return data and 200 OK
            else:
                return {'status': 402, 'response': "Invalid password."}, 402
            
api.add_resource(LogIn, '/login', endpoint='login')


class Characters(Resource):
    
    def get(self):
        parser = reqparse.RequestParser()  # initialize
        parser.add_argument('characterId', type=str, action='append', help='Missing argument characterId', required=False,location = 'args')
        parser.add_argument('characterName', type=str, action='append', help='Missing argument characterName', required=False,location = 'args') 
        args = parser.parse_args()  # parse arguments to dictionary

        data = pd.read_csv('data.csv', dtype=({
            'Character ID' : 'str'}))  # read local CSV

        # if user is not providing any information about the character(s) wanted
        if args['characterId'] is None and args['characterName'] is None:        
            data = data.to_dict(orient='records') # Convert data to dict
            return {'status': 200, 'response': data}, 200 # return data and 200 OK
        
        else:
            characters_to_retrieve = [] # to store what the user wants
            
            if args['characterId'] is not None:
                #check if the IDs asked are in the dataframe
                if all(elem in list(data['Character ID']) for elem in args['characterId']):
                    entry = data.loc[data['Character ID'].isin(args['characterId'])] # retrieve entry with productId
                    entry = entry.to_dict(orient='records') # convert dataframe to dict
                    characters_to_retrieve.append(entry)
                else:
                    diff = set(args['characterId']).difference(set(data['Character ID'])) 
                    return {'status': 404, 'response': f"{diff} is not in our database"}, 404


            if args['characterName'] is not None:
                #check if the names asked are in the dataframe                
                if all(elem in list(data['Character Name']) for elem in args['characterName']):
                    entry = data.loc[data['Character Name'].isin(args['characterName'])] # retrieve entry with productId
                    entry = entry.to_dict(orient='records') # convert dataframe to dict
                    characters_to_retrieve.append(entry)
                else:
                    diff = set(args['characterName']).difference(set(data['Character Name']))
                    return {'status': 404, 'response': f"{diff} is not in our database"}, 404
                
            
            return {'status': 200, 'response': characters_to_retrieve}, 200 # return data and 200 OK
        
        
    @jwt_required()  #Oauth
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('Authorization', type=str, help='Access token required', required=True, location ='headers')
        parser.add_argument('characterName', type=str, help='Missing argument characterName', required=False,location = 'args')
        parser.add_argument('characterId', type=str, help='Missing argument characterId', required=True,location = 'args')
        parser.add_argument('number_events', type=int, help='Missing argument number_events', required=False,location = 'args')
        parser.add_argument('number_series', type=int, help='Missing argument number_series', required=False,location = 'args')
        parser.add_argument('number_comics', type= int, help='Missing argument number_comics', required=False,location = 'args')
        parser.add_argument('highest_price', type=float, help='Missing argument highest_price', required=False,location = 'args')
        args = parser.parse_args()  # parse arguments to dictionary

        data = pd.read_csv('data.csv', dtype=({
            'Character ID' : 'str'}))  # read local CSV
        
        # 1st case: the ID provided by the client is already present in the dataframe:
        if args['characterId'] in list(data['Character ID']):
            return {'status': 409, 'response': f"'{args['characterId']}' already exists."}, 409
        
        else:
            # 2nd: the client provides all the necessary information to add a new character in the dataframe:
            if (args['characterName'] is not None) and (args['number_comics'] is  not None) and (args['number_events'] is not None) and (args['number_series'] is  not None) and (args['highest_price'] is  not None):
                entry = pd.DataFrame({
                'Character Name': [args['characterName']],
                'Character ID': [args['characterId']],
                'Total Available Events': [args['number_events']],
                'Total Available Series': [args['number_series']],
                'Total Available Comics': [args['number_comics']],
                'Price of the Most Expensive Comic': [args['highest_price']]})
                data = data.append(entry, ignore_index=True) # add entry to database
                data.to_csv('data.csv', index=False)  # save back to CSV
                entry = data.loc[data['Character ID']==args['characterId']] # retrieve entry with productId
                entry = entry.to_dict(orient='records') # convert dataframe to dict
                return {'status': 200, 'response': entry}, 200 # return data and 200 OK 
            
            # 3rd case: the client only provides the ID of the character she/he wants to add in the dataframe:
            if (args['characterName'] is None) and (args['number_comics'] is None) and (args['number_events'] is None) and (args['number_series'] is None) and (args['highest_price'] is None): 
                
                # accessing the Marvel API
                
                public_key = '78250442652c008eed20664b4d2b9b9e'
                private_key = '14d25b635eb90f60a4ea54a898d90e66c6114ae9'
                #let's create a timestamp:
                ts = datetime.datetime.now()
                #convert ts into a string:
                ts = ts.strftime("%d/%m/%Y%H:%M:%S")
                #let's concatenate the variables and create the hash:
                hash_parameter = ts+private_key+public_key
                hash_encoded = hashlib.md5(hash_parameter.encode('utf-8')).hexdigest()
                
                params={'apikey': public_key,
                           'ts': ts,
                           'hash': hash_encoded}
                
                url_character= 'http://gateway.marvel.com/v1/public/characters/'+str(args['characterId'])
                response_character = requests.get(url_character, params=params)
                

                url_price = 'http://gateway.marvel.com/v1/public/characters/'+str(args['characterId'])+'/comics'
                params['characterId'] = args['characterId']
                response_price = (requests.get(url_price,params=params))

                if response_character.status_code == 404:
                    return {'status': 404, 'response': 'Error: Character ID not found'}, 404

                if response_character.status_code == 200 and response_price.status_code==200:
                    response_price= response_price.json()['data']['results']
                    response_character = response_character.json()['data']['results']
                    
                    if response_character[0]['comics']['available'] != 0:
                        # finding the highest price
                        price = []
                        for comic_id in response_price: 
                            for comic_price in comic_id['prices']: 
                                price.append(float(comic_price['price']))
                                highest_price_comic = (max(price))
                                
                    else:
                        highest_price_comic = None



                    add_char = pd.DataFrame({'Character Name': [response_character[0]['name']],
                                           'Character ID': [args['characterId']],
                                          'Total Available Events':[response_character[0]['events']['available']],
                                          'Total Available Series':[response_character[0]['series']['available']],
                                          'Total Available Comics':[response_character[0]['comics']['available']],
                                          'Price of the Most Expensive Comic':highest_price_comic})

                    data = data.append(add_char, ignore_index=True) # add entry to dataset
                    data.replace(0.00, None, inplace=True)
                    data.replace(0, None, inplace=True)
                    data = data.astype({
                        'Character ID' : 'str'})
                    data.to_csv('data.csv', index=False)  # save the updated dataset to CSV
                    entry = data.loc[data['Character ID']==args['characterId']]
                    entry = entry.to_dict(orient='records')
                    return {'status': 200, 'response': entry}, 200 # return data and 200 OK

                else:
                    return {'status': 401, 'response': 'Connection not enstablished'}, 401
            else:  
                return {'status': 402, 'response': 'Insufficient Information Input'}, 402

 
    @jwt_required() #Oauth
    def delete(self):
        parser = reqparse.RequestParser()   
        parser.add_argument('Authorization', type=str, help='Access token required', required=True, location ='headers')
        parser.add_argument('characterId', type=str, help='Missing argument characterId', required=False,location='args', action='append')
        parser.add_argument('characterName', type=str, help='Missing argument characterName', required=False,location='args', action='append')
        args = parser.parse_args()  # parse arguments to dictionary
        
        data = pd.read_csv('data.csv', dtype=({
            'Character ID' : 'str'}))  # read local CSV
        
        if args['characterName'] is None and args['characterId'] is None: 
            return {'status': 404, 'response': "Missing argument characterId or characterName."}, 404
        # the user needs to give us at list one ID or at least one name
        else:
            if args['characterName'] is not None:
                if all(elem in list(data['Character Name']) for elem in args['characterName']):
                    data = data.loc[data['Character Name'].isin(args['characterName']) == False]
                    data.to_csv('data.csv', index = False)

                else: 
                    diff = set(args['characterName']).difference(set(data['Character Name'])) 
                    return {'status': 405, 'response': f'Character Name {diff} not found'}, 405

            if args['characterId'] is not None:
                if all(elem in list(data['Character ID']) for elem in args['characterId']):
                    data = data.loc[data['Character ID'].isin(args['characterId']) == False]
                    data.to_csv('data.csv', index = False)

                else: 
                    diff = set(args['characterId']).difference(set(data['Character ID'])) 
                    return {'status': 405, 'response': f'Character ID {diff} not found'}, 405
                
            return {'status': 200, 'response': data.to_dict(orient = 'records') }, 200


    @jwt_required()    
    def put(self):  
        parser = reqparse.RequestParser()  
        parser.add_argument('Authorization', type=str, help='Access token required', required=True, location ='headers')        
        parser.add_argument('characterId', type=str, help='Missing argument characterId', required=False,location='args')
        parser.add_argument('characterName', type=str, help='Missing argument characterName', required=False,location='args')
        parser.add_argument('original_currency',type=str,help='Missing argument original_currency',required=True,location='args') 
        parser.add_argument('wanted_currency', type=str, help='Missing argument wanted_currency', required=True,location='args')
        
        args = parser.parse_args() 
        
        data = pd.read_csv('data.csv', dtype=({'Character ID' : 'str'}))
        
        url = "https://api.apilayer.com/exchangerates_data/convert"
            
        payload = {
                'from' : args['original_currency'],
                'to': args['wanted_currency']
            }
                                              
        headers= {'apikey' :'0jwSmSh9cCM50ozV8oq7h4eUc0pZ5Us5'}
       
        if args['characterName'] is None and args['characterId'] is None: 
            return {'status': 404, 'response': "Missing argument characterId or characterName."}, 404
        
        else:
            
            if args['characterName'] is not None:
                if args['characterName'] in list(data['Character Name']):
                    data = pd.read_csv('data.csv', dtype=({'Character ID' : 'str'}))
                    data['my_column_duplicate'] = data.loc[:, 'Character Name']
                    data.set_index('my_column_duplicate', inplace = True)
                    original_price = data.loc[args['characterName'],'Price of the Most Expensive Comic']
                    payload['amount'] = str(original_price)
                    response = requests.get(url, headers = headers, params = payload).json()
                    converted_price = response["result"]
                    data.at[args['characterName'],'Price of the Most Expensive Comic']=float(round(converted_price, 2))
                    data.to_csv('data.csv', index = False)
                else: 
                    return {'status': 405, 'response': f'Character Name not found'}, 405


            if args['characterId'] is not None:
                if args['characterId'] in list(data['Character ID']):
                    data = pd.read_csv('data.csv', dtype=({'Character ID' : 'str'}))
                    data['my_column_duplicate'] = data.loc[:, 'Character ID']
                    data.set_index('my_column_duplicate', inplace = True)
                    original_price = data.loc[args['characterId'],'Price of the Most Expensive Comic']
                    payload['amount'] = str(original_price)
                    response = requests.get(url, headers = headers, params = payload).json()
                    converted_price = response["result"]
                    data.at[args['characterId'],'Price of the Most Expensive Comic']=float(round(converted_price, 2))
                    data.to_csv('data.csv', index = False)
                else:
                    return {'status': 405, 'response': f'Character ID not found'}, 405
                
            return {'status': 200, 'response': data.to_dict(orient = 'records') }, 200        
        
api.add_resource(Characters, '/characters', endpoint='characters')

if __name__ == '__main__':
    app.run(debug=True)