from carto.auth import APIKeyAuthClient
from carto.sql import SQLClient
from parameters.credentials import CARTO_API_KEY

### BEGIN Functions for modifying individual records on Carto
def delete_from_carto_by_id(asset_id):
    auth_client = APIKeyAuthClient(api_key=CARTO_API_KEY, base_url=USR_BASE_URL)
    sql = SQLClient(auth_client)
    results = sql.send(f"DELETE from {TABLE_NAME} WHERE id ='{asset_id}'")
    return results

def update_asset_on_carto(asset, fields):
    auth_client = APIKeyAuthClient(api_key=CARTO_API_KEY, base_url=USR_BASE_URL)
    sql = SQLClient(auth_client)
    #values_tuple_strings = [make_values_tuple_string_from_model(r, fields) for r in [asset]]
    # OR POSSIBLY
    #values_tuple_strings = [make_values_tuple_string_from_model(asset, fields)]


    #q = f"UPDATE {TABLE_NAME} SET {values_tuple_strings} WHERE asset_id = {asset.id};"

    values_tuple_strings = [values_string_from_model(asset, fields)]
    q = f"UPDATE {TABLE_NAME} SET ({', '.join(fields + ['the_geom', 'the_geom_webmercator'])}) " \
        f"VALUES {', '.join(map(lambda x: x + 1, values_tuple_strings))};"

    print(q)
    assert len(q) < 16384
    raise ValueError("Halting here (update_asset_on_carto) to catch our breath.")
    #####results = sql.send(q)

def insert_new_assets_into_carto(sql, table_name, assets, fields):
    # q = f"INSERT INTO {table_name} (id, name, asset_type, asset_type_title, category, category_title, latitude, longitude) VALUES (202020, 'Zyzzlvaria Zoo', 'zoo', 'animal places', 'cool_stuff', 'Cool Stuff', 40.5195849005734, -80.0445997570883 );"
    # results = sql.send(q)

    # Example of how to insert a single record:
    # q = f"INSERT INTO {table_name} (id, name, asset_type, asset_type_title, category, category_title, latitude, longitude) VALUES (112644, 'Ormsby Pool and Recreation Center', 'rec_centers', 'Rec Centers', 'civic', 'Civic', 40.4290817, -79.97429357);"

    # Batch inserts can be done like this:
    # INSERT INTO election_results (county_id,voters,pro)
    # VALUES  (1, 11,8),
    #        (12,21,10),
    #        (78,31,27);

    # map set of records into value tuple strings
    #values_tuple_strings = [make_values_tuple_string(r, fields) for r in records]

    values_tuple_strings = [values_string(a, fields) for a in assets]

    q = f"INSERT INTO {table_name} ({', '.join(fields + ['the_geom', 'the_geom_webmercator'])}) " \
        f"VALUES {', '.join(map(lambda x: x + 1, values_tuple_strings))};"

    assert len(q) < 16384
    pprint(q)
    raise ValueError("Halting here (insert_new_assets_into_carto) to catch our breath.")
    results = sql.send(q)


### END Functions for modifying individual records on Carto