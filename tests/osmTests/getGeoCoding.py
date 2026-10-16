import osm_data as osm
import time

import traceback

time_start = time.time()

#addresses = [ 'Schönwalde,16348,DE', 'Klosterfelde', 'Marchlewskistr. 43, 10243 Berlin']
coords = (  52.7965937,  13.4801974)
#coords = (65.4907405194034, -17.74639390625)            
addresses = [ 'Gröden,04932']


try:

    conf = osm.Config(optFile='logisticsLab.yml')

    print('get coordinates')
    osmData = osm.Geocoding()
    status, msg= osmData.loadCoordinates(addresses)

    if status!=200:
        print(msg)
    else:
        coordinates = osmData.coordinates
        print(coordinates)

    print('get search results')
    status, msg= osmData.search(addresses[0])

    if status!=200:
        print(msg)
    else:
        addr = osmData.results
        print(addr)

        addrList = osmData.addresses
        print(addrList)

    print('get reverse results')
    status, msg= osmData.reverse(coords)

    if status!=200:
        print(msg)
    else:
        addr = osmData.results
        print(addr)


except osm.OsmException as e: 
    print(e)
    traceback.print_exc()


print("... done {}".format(time.time() - time_start))
