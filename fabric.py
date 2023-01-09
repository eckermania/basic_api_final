from flask import *
from google.cloud import datastore
import json
import constants
from json2html import *
from flask import Flask, render_template, request

datastore_client = datastore.Client()

bp = Blueprint('fabric', __name__, url_prefix='/fabrics')

@bp.route('', methods=['POST','GET'])
def fabrics_get_post():
    if 'application/json' not in request.accept_mimetypes:
        return ({'Error': 'Accept MIME type not supported'}, 406)

    # Create a fabric record
    if request.method == 'POST':
        content = request.get_json()

        if "substrate" not in content.keys() or "color" not in content.keys() or "yards" not in content.keys():
            return({'Error': 'The request object is missing at least one of the required attributes'}, 400)

        # Create new record in db
        new_fabric = datastore.entity.Entity(key=datastore_client.key(constants.fabrics))
        new_fabric.update({"substrate": content["substrate"], "color": content["color"],
            "yards": content["yards"]})
        datastore_client.put(new_fabric)

        # Add attributes to return
        content['id'] = str(new_fabric.key.id)
        content['patterns'] = []
        content['self'] = request.base_url + '/' + str(new_fabric.key.id)
        return (content, 201)

    # View all fabric
    elif request.method == 'GET':
        query = datastore_client.query(kind=constants.fabrics)
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

        # Get total number of records
        count_query = datastore_client.query(kind=constants.fabrics)
        count_results = list(count_query.fetch())
        count = len(count_results)
        
        for e in results:
            e["self"] = request.base_url + '/' + str(e.key.id)
            e["id"] = str(e.key.id)
            if 'patterns' not in e or len(e['patterns']) == 0:
                e['patterns'] = []
            else:
                pattern_list = []
                for pattern_id in e['patterns']:
                    pattern_key = datastore_client.key(constants.patterns, int(pattern_id))
                    pattern = datastore_client.get(key=pattern_key)
                    pattern_list.append(pattern)
                
                e['patterns'] = pattern_list

        output = {"fabrics": results}
        if next_url:
            output["next"] = next_url

        output["total_items"] = count

        res = make_response(json.dumps(output))
        res.headers.set('Content-Type', 'application/json')

        return (res, 200)

    else:
        return ('', 405)

@bp.route('/<id>', methods=['GET','DELETE', 'PATCH', 'PUT'])
def fabrics_get_delete_update(id):
    if 'application/json' not in request.accept_mimetypes:
        return ({'Error': 'Accept MIME type not supported'}, 406)

    fabric_key = datastore_client.key(constants.fabrics, int(id))
    fabric = datastore_client.get(key=fabric_key)

    if fabric is None:
        return ({'Error': 'No fabric with this fabric_id exists'}, 404)

    # Delete a fabric
    # Deleting a fabric will remove the fabric id from any associated pattern records
    if request.method == 'DELETE':
        key = datastore_client.key(constants.fabrics, int(id))

        if 'patterns' in fabric.keys() and len(fabric['patterns']) > 0:
            for e in fabric['patterns']:
                pattern_key = datastore_client.key(constants.patterns, int(e))
                pattern = datastore_client.get(key=pattern_key)

                pattern['fabric'] = None
                datastore_client.put(pattern)

        datastore_client.delete(key)
        return ('',204)

    # View a fabric
    elif request.method == 'GET':
        if 'patterns' not in fabric.keys():
            fabric['patterns'] = []
        else:
            pattern_list = []
            for pattern_id in fabric['patterns']:
                pattern_key = datastore_client.key(constants.patterns, int(pattern_id))
                pattern = datastore_client.get(key=pattern_key)
                pattern_list.append(pattern)
            
            fabric['patterns'] = pattern_list

        fabric['id'] = str(fabric.id)
        fabric['self'] = request.base_url

        res = make_response(json.dumps(fabric))
        res.headers.set('Content-Type', 'application/json')

        return (res, 200)

    # Update a fabric - only updates/overwrites attributes contained in request body
    elif request.method == 'PUT' or request.method == 'PATCH':
        content = request.get_json()
        for attribute in content.keys():
            fabric[attribute] = content[attribute]

        datastore_client.put(fabric)

        if "patterns" not in fabric.keys():
            content['patterns'] = []
        else:
            pattern_list = []
            for pattern_id in fabric['patterns']:
                pattern_key = datastore_client.key(constants.patterns, int(pattern_id))
                pattern = datastore_client.get(key=pattern_key)
                pattern_list.append(pattern)
            
            fabric['patterns'] = pattern_list

        for attribute in fabric.keys():
            content[attribute] = fabric[attribute]

        content['id'] = fabric_key.id
        self_url = request.base_url
        content['self'] = self_url
        res = make_response(json.dumps(content))
        res.headers.set('Content-Type', 'application/json')

        return (res, 200)

    else:
        return ('', 405)