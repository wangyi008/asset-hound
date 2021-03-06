import csv
import os
import re
import sys  # This is a workaround for an error that

import phonenumbers
from django.conf import settings
from django.core.management.base import BaseCommand

from assets.models import (Asset,
                           Organization,
                           Location,
                           AssetType,
                           Tag,
                           ProvidedService,
                           TargetPopulation,
                           DataSource)

csv.field_size_limit(sys.maxsize)  # looks like this:

from assets.management.commands.util import parse_cell
from assets.management.commands.clear_and_load_by_type import get_location_by_keys, update_or_create_location
from assets.utils import geocode_address # This uses Geocod.io

# _csv.Error: field larger than field limit (131072)

def form_full_address(row):
    maybe_malformed = False
    if 'city' in row:
        city = row['city']
    elif 'municipality' in row:
        city = row['municipality']

    if 'state' in row:
        state = row['state']
    else:
        state = 'PA'

    return "{}, {}, {} {}".format(row['street_address'], city, state, row['zip_code'])

def split_location(location_id, dry_run):
    """Split the Location with ID location_id, by finding all the associated Assets,
    pulling their correct address information from the RawAsset (assuming there's
    just 1), and finding or generating a suitable new location to link to and
    fix up, adding new geocoordinates if necessary. If the Location is only linked to
    by one Asset, that Location should just get its geocoordinates cleaned up, as needed."""

    overloaded_location = Location.objects.get(pk=location_id)
    total = len(overloaded_location.asset_set.all())
    print(f"Attempting to generate better Locations for {total} Assets.")

    assets_handled = 0
    for asset in overloaded_location.asset_set.all():
        if asset.do_not_display is True: # These may not have RawAssets
            continue # and we don't need to worry about these Assets.
        raw_assets = list(asset.rawasset_set.all())
        if len(raw_assets) == 0:
            raise ValueError(f"The asset with ID {asset.id} has no linked raw assets!")
        if len(raw_assets) > 1:
            raise ValueError(f"The asset with ID {asset.id} has multiple linked raw assets!")
            # Next step here is to pull all the location data and see if it's consistent
            # enough to be auto-joined into a single location.
        raw_asset = raw_assets[0]
        row = {'parcel_id': raw_asset.parcel_id,
                'street_address': raw_asset.street_address,
                #'unit' = raw_asset.unit, # not yet supported
                #'unit_type' = raw_asset.unit_type, # not yet supported
                #'municipality' = raw_asset.municipality, # not yet supported
                'city': raw_asset.city,
                'state': raw_asset.state,
                'zip_code': raw_asset.zip_code,
                'available_transportation': raw_asset.available_transportation,
                'latitude': raw_asset.latitude,
                'longitude': raw_asset.longitude,
                'residence': raw_asset.residence,
                'geocoding_properties': raw_asset.geocoding_properties,
                'parcel_id': raw_asset.parcel_id,
                }
        # Try to find a matching extant location
        keys = ['street_address__iexact', 'city__iexact', 'state__iexact', 'zip_code__startswith']
        location, location_obtained = get_location_by_keys(row, keys)
        if row['street_address'] in [None, '']:
            if row['latitude'] not in [None, ''] and (row['geocoding_properties'] is None or "'confidence'" not in row['geocoding_properties']):
                # If there's no street address, but there are legit coordinates in the RawAsset, just generate a Location from that.
                location = Location(**row)
                location._change_reason = 'Regenerating locations (bad initial Location assignment)'
                if not dry_run:
                    location.save()
                location_obtained = True
                location_created = True
            else:
                print(row)
                assert "'confidence'" in row['geocoding_properties']
                assert row['street_address'] is None
                #assert row['city'] is None
                #assert row['state'] is None
                #assert row['zip_code'] is None
                # This is just a RawAsset that has insufficient valid location information. Therefore we should set location = None.
                # (This is kind of a fix for an assignment that never should have happened in the first place.)
                location = None
                location_obtained = True

        if not location_obtained: # If none comes up, create a new one. # But shouldn't one always come up?
            print("This can happen since the address in the existing Location can deviate from that in the RawAsset due to editing.")
            # Example of when this can happen:
            #    I don't know why, but this fails
            #    >> get_location_by_keys({'street_address__iexact': '1501 Buena Vista  Road'}, ['street_address__iexact'])
            #    (None, False)

            #    while this succeeds:
            #    >>> get_location_by_keys({'street_address': '1501 Buena Vista  Road'}, ['street_address'])
            #    (<Location: 1501 Buena Vista  Road Pittsburgh, PA >, True)

            # In this instance, just try falling back to the original location.
            if total > 1:
                print(f"  Check whether the Assets at location ID {location_id} should really be together (which is what is being assumed here because it looks like some hand-editing has occurred).")
            location = overloaded_location
            location_obtained = True
            # This can happen when the address information in the RawAsset has been edited
            # to get the address information in the Location.
            # Basically this is where consistent address standardization would be a big help.

            #else: # However, sometimes there are more, so this should work:
            #    keys = ['street_address', 'city__iexact', 'state__iexact', 'zip_code__startswith']
            #    location, location_obtained = get_location_by_keys(row, keys)
            #    assert location_obtained


            #kwargs = row
            #if 'street_address' in row and row['street_address'] not in [None, '']:
            #    full_address = form_full_address(row)
            #    # Try to geocode with Geocod.io
            #    latitude, longitude, properties = geocode_address(full_address)
            #    kwargs['latitude'] = latitude
            #    kwargs['longitude'] = longitude
            #    kwargs['geocoding_properties'] = 'Geocoded by Geocodio'
            #    location = Location(**kwargs)
            #    location._change_reason = 'Regenerating locations (bad initial Location assignment)'
            #    if not dry_run:
            #        location.save()
            #    location_obtained = True
            #    location_created = True

        if location_obtained:
            if location is not None:
                if location.latitude is None or (location.geocoding_properties is not None and "'confidence'" in location.geocoding_properties): # That is,
                #if it's a Pelias geocoding (and therefore questionable).
                # If polygon boundaries are added to the Location model, a check for those should also possibly be added here.
                    if 'street_address' in row and row['street_address'] not in [None, '']:
                        full_address = form_full_address(row)
                        # Try to geocode with Geocod.io
                        latitude, longitude, properties = geocode_address(full_address)
                        if latitude is None:
                            print(f"Geocoordinates for Location ID {location.id} are being set to (None, None).")
                        location.latitude = latitude
                        location.longitude = longitude
                        if latitude is None:
                            location.geocoding_properties = 'Unsuccessfully geocoded by Geocodio'
                        else:
                            location.geocoding_properties = properties
                        location._change_reason = 'Regenerating locations (bad initial Location assignment)'
                        if not dry_run:
                            location.save()
            asset.location = location
            asset._change_reason = 'Regenerating locations (bad initial Location assignment)'
            if not dry_run:
                asset.save()
            assets_handled += 1

    print(f"Handled {assets_handled}/{total} asset locations. (Some may have been pre-existing.)")
    return assets_handled

class Command(BaseCommand):
    help = """For a given location_id, find all the linked Assets, pull their RawAssets and attempt to
    generate new Location instances from the location fields in the RawAsset."""

    def add_arguments(self, parser): # Necessary boilerplate for accessing args.
        parser.add_argument('args', nargs='*')

    def handle(self, *args, **options):
        dry_run = False
        if len(args) != 1:
            raise ValueError("This script accepts exactly one command-line argument, which should be a valid Location ID.")
        split_location(args[0], dry_run)
