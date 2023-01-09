from flask import *
from google.cloud import datastore
import json
import constants
from flask import Flask, render_template, request
from google.oauth2 import id_token
from google.auth.transport import requests

client_id = '1063937657970-9uo6as8tfjckg11qu2q1k4crnc3nsbqo.apps.googleusercontent.com'

datastore_client = datastore.Client()

bp = Blueprint('pattern', __name__, url_prefix='/patterns')

@bp.route('', methods=['POST','GET'])
def patterns_get_post():
    
    # Client does not accept JSON
    if 'application/json' not in request.accept_mimetypes :
        return ({'Error': 'Accept MIME type not supported'}, 406)

    bearer_token = request.headers.get('Authorization')

    if bearer_token is None:
        return('', 401)
    
    token = bearer_token.replace('Bearer ', '')

    try:
        # Specify the CLIENT_ID of the app that accesses the backend:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), client_id)

        # ID token is valid. Get the user's Google Account ID from the decoded token.
        userid = idinfo['sub']

        # Create a pattern record
        if request.method == 'POST':

            content = request.get_json()

            if "name" not in content.keys() or "garment" not in content.keys() or "company" not in content.keys():
                return({'Error': 'The request object is missing at least one of the required attributes'}, 400)

            # Create new record in db
            new_pattern = datastore.entity.Entity(key=datastore_client.key(constants.patterns))
            new_pattern.update({"name": content["name"], "garment": content["garment"],
                "company": content["company"], "maker": userid})
            datastore_client.put(new_pattern)

            # Add attributes to return
            content['id'] = str(new_pattern.key.id)
            content['fabric'] = None
            content['maker'] = userid
            content['self'] = request.base_url + '/' + str(new_pattern.key.id)
            return (content, 201)

        # View all patterns belonging to user
        elif request.method == 'GET':
            query = datastore_client.query(kind=constants.patterns)
            query.add_filter("maker", "=", userid)
            q_limit = int(request.args.get('limit', '5'))
            q_offset = int(request.args.get('offset', '0'))
            l_iterator = query.fetch(limit=q_limit, offset=q_offset)
            pages = l_iterator.pages
            results = list(next(pages))

            if l_iterator.next_page_token:
                next_offset = q_offset + q_limit
                next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
            else:
                next_url = None
            
            for e in results:
                e["self"] = request.base_url + '/' + str(e.key.id)
                e["id"] = str(e.key.id)
                if 'fabric' not in e or e['fabric'] is None:
                    e['fabric'] = None
                else:
                    fabric_key = datastore_client.key(constants.fabrics, int(e['fabric']))
                    fabric = datastore_client.get(key=fabric_key)
                    e['fabric'] = fabric

            output = {"patterns": results}
            if next_url:
                output["next"] = next_url

            # Get count of patterns
            count_query = datastore_client.query(kind=constants.patterns)
            count_query.add_filter("maker", "=", userid)
            count_results = list(count_query.fetch())
            output["total_items"] = len(count_results)
            
            res = make_response(json.dumps(output))
            res.headers.set('Content-Type', 'application/json')

            return (res, 200)

        else:
            return ('', 405)
    
    except ValueError:
        # Invalid token
        return('', 401)


@bp.route('/<id>', methods=['GET','DELETE', 'PATCH', 'PUT'])
def patterns_get_delete_update(id):

    if 'application/json' not in request.accept_mimetypes:
        return ({'Error': 'Accept MIME type not supported'}, 406)

    bearer_token = request.headers.get('Authorization')

    if bearer_token is None:
        return('', 401)
    
    token = bearer_token.replace('Bearer ', '')

    pattern_key = datastore_client.key(constants.patterns, int(id))
    pattern = datastore_client.get(key=pattern_key)

    if pattern is None:
        return ({'Error': 'No pattern with this pattern_id exists'}, 404)

    try:
        # Specify the CLIENT_ID of the app that accesses the backend:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), client_id)
        
        # ID token is valid. Get the user's Google Account ID from the decoded token.
        userid = idinfo['sub']

        if userid != pattern['maker']:
            return({'Error': 'You are not authorized to access this resource'}, 403)

        # Delete a pattern
        # Deleting a pattern will remove the pattern id from any associated fabric records
        if request.method == 'DELETE':
            key = datastore_client.key(constants.patterns, int(id))

            if 'fabric' in pattern.keys() and pattern['fabric'] is not None:
                print('PATTERN[FABRIC]>>>>', pattern['fabric'])
                fabric_key = datastore_client.key(constants.fabrics, int(pattern['fabric']))
                print('FABRIC_KEY', fabric_key)
                fabric = datastore_client.get(key=fabric_key)

                fabric['patterns'].remove(id)
                datastore_client.put(fabric)

            datastore_client.delete(key)
            return ('',204)

        # View a pattern
        elif request.method == 'GET':
            if 'fabric' not in pattern.keys():
                pattern['fabric'] = []
            else:
                fabric_key = datastore_client.key(constants.fabrics, int(pattern['fabric']))
                fabric = datastore_client.get(key=fabric_key)
                pattern['fabric'] = fabric

            pattern['id'] = str(pattern.id)
            pattern['self'] = request.base_url

            res = make_response(json.dumps(pattern))
            res.headers.set('Content-Type', 'application/json')

            return (res, 200)

        # Update a pattern - only updates/overwrites attributes contained in request body
        elif request.method == 'PUT' or request.method == 'PATCH':
            content = request.get_json()
            for attribute in content.keys():
                pattern[attribute] = content[attribute]

            datastore_client.put(pattern)

            if "fabric" not in pattern.keys():
                content['fabric'] = []
            else:
                fabric_key = datastore_client.key(constants.fabrics, int(pattern['fabric']))
                fabric = datastore_client.get(key=fabric_key)
                pattern['fabric'] = fabric

            for attribute in pattern.keys():
                content[attribute] = pattern[attribute]

            content['id'] = pattern_key.id
            self_url = request.base_url
            content['self'] = self_url
            res = make_response(json.dumps(content))
            res.headers.set('Content-Type', 'application/json')

            return (res, 200)

        else:
            return ('', 405)
    
    except ValueError:
        # Invalid token
        return('', 401)


@bp.route('/<pid>/fabrics/<fid>', methods=['PUT', 'PATCH', 'DELETE'])
def patterns_fabrics_join_delete(pid, fid):

    if 'application/json' not in request.accept_mimetypes:
        return ({'Error': 'Accept MIME type not supported'}, 406)

    bearer_token = request.headers.get('Authorization')

    if bearer_token is None:
        return('', 401)
    
    token = bearer_token.replace('Bearer ', '')

    pattern_key = datastore_client.key(constants.patterns, int(pid))
    pattern = datastore_client.get(key=pattern_key)

    fabric_key = datastore_client.key(constants.fabrics, int(fid))
    fabric = datastore_client.get(key=fabric_key)

    if fabric is None or pattern is None:
        return({'Error': 'No pattern with this pattern_id exists or no fabric with this fabric_id exists'}, 404)

    try:
        # Specify the CLIENT_ID of the app that accesses the backend:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), client_id)
        
        # ID token is valid. Get the user's Google Account ID from the decoded token.
        userid = idinfo['sub']

        if userid != pattern['maker']:
            return({'Error': 'You are not authorized to access this resource'}, 403)

        # Create a new join between a pattern and fabric
        if request.method == 'PUT' or request.method == 'PATCH':
            if 'fabric' in pattern.keys():
                return({'Error': 'There is already a fabric assigned to this pattern'}, 403)

            pattern['fabric'] = fid
            datastore_client.put(pattern)

            if 'patterns' in fabric.keys():
                fabric['patterns'].append(pid)
            else:
                fabric['patterns'] = [pid]
            
            datastore_client.put(fabric)

            pattern['fabric'] = fabric
            
            pattern['self'] = request.root_url + 'patterns/' + str(pattern.key.id)
            pattern['id'] = pattern.key.id

            res = make_response(json.dumps(pattern))
            res.headers.set('Content-Type', 'application/json')

            return (res, 200)

        # Remove join between a pattern and fabric
        if request.method == 'DELETE':
            if 'fabric' not in pattern.keys():
                return({'Error': 'There is no fabric to remove from this pattern'}, 403)

            if pattern['fabric'] != fid:
                return({'Error': 'This fabric_id is not associated with this pattern'}, 403)

            pattern['fabric'] = None
            datastore_client.put(pattern)

            fabric['patterns'].remove(pid)
            datastore_client.put(fabric)

            return('', 204)

        else:
            return ('', 405)

    except ValueError:
        # Invalid token
        return('', 401)