import tornado.ioloop
import tornado.web
from mystaticfilehandler import MyStaticFileHandler
from random import randint, choice
from plotly_skylog import PlotlySkylog
from safety_metadata_functions import *
from skylog import DroneLogParser
from skylog_safety_metadata import SkylogSafetyMetadata
from skylog_sources import MongoSource
from log_parsers.DJI.DjiLogExtractor import DjiLogExtractor
from log_parsers.utils.global_time import get_datetime_with_timezone
from collections import OrderedDict
from safety_score_parser import get_safety_score_breakdown


mongo_source = MongoSource()


class SkylogWrapper:
    drone_log_parser = None
    file_path = None
    plotly_skylog = None
    metadata_supplier = None


def choose_random_flightlog():
    db = mongo_source.client['flight_logs']
    characters = 'abcdef1234567890'
    random = choice(characters) + choice(characters) + choice(characters)
    return [db.flights.find_one({"log_file": {"$regex": random}}, {"log_file": 1})['log_file']]


def get_and_convert_flightlog_time(flight):
    dateTime = get_datetime_with_timezone((float(flight['metadata']['start_time'])) / 1000,
                                          float(flight['flight_records'][0]['location']['lat']),
                                          float(flight['flight_records'][0]['location']['lng']))
    dateTime = str(dateTime)[:16]
    dateTime = dateTime[:4] + dateTime[5:7] + dateTime[8:10] + dateTime[11:13] + dateTime[14:16]
    return int(dateTime)


def sort_flights_by_datetime(flightArray):
    flightDictionary = dict(flightArray)
    return OrderedDict((k, v) for k, v in sorted(flightDictionary.items(), key=lambda x: x[1], reverse=True))


def get_safety_score_feedback(filename):
    db = mongo_source.client['flight_analysis']
    return  db.analytics.find_one({'log_file': filename},{'_id': 0, 'Feedback':1, 'Score':1})


class MapHandler(tornado.web.RequestHandler):
    MISSING_FILE_ERROR_CODE = 400
    BAD_LAMBDA_ERROR_CODE = 401
    NO_SKYLOG_GIST_YET_ERROR_CODE = 402
    FLIGHT_DOES_NOT_BELONG_TO_USER = 403

    def initialize(self, data):
        self.wrapper = data

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')


    def get(self):
        lambda_text = self.get_query_arguments('lambda')
        file_path = self.get_query_arguments('filepath')
        user = self.get_query_arguments('user')
        signedIn = int(self.get_query_arguments('signedIn')[0])
        randomFlight = int(self.get_query_arguments('randomFlight')[0])

        try:
            if not file_path == self.wrapper.file_path:

                startFull = time.time()
                if randomFlight:
                    file_path = choose_random_flightlog()
                print(time.time()-startFull)

                start2 = time.time()
                self.wrapper.drone_log_parser = DroneLogParser(file_path[0], mongo_source,
                                                [DjiLogExtractor], ignore_source=False)
                print(time.time()-start2)
                self.wrapper.file_path = file_path
        except ValueError as e:
            print(e.message)
            raise tornado.web.HTTPError(self.MISSING_FILE_ERROR_CODE)
        except IOError as e:
            print(e.message)
            raise tornado.web.HTTPError(self.MISSING_FILE_ERROR_CODE)


        try:
            lambda_input = None
            if lambda_text and lambda_text[0]:
                lambda_input = eval(lambda_text[0])
            flight = self.wrapper.drone_log_parser.get_flight()

            if self.wrapper.drone_log_parser.fetched:
                if flight.get_meta_data()['username'] != user[0] and signedIn == 1 and randomFlight == 0:
                    raise tornado.web.HTTPError(self.FLIGHT_DOES_NOT_BELONG_TO_USER)

            flight.get_combined_records()
            plotly_skylog = PlotlySkylog(flight.get_combined_records(), flight.get_meta_data())
            clean_file_name = os.path.basename(file_path[0])

            metadata_supplier = SkylogSafetyMetadata(flight,
                                                     [
                                                         ('Drone Type', get_max_throttle),
                                                         ('Safety Score', get_safety_score),
                                                         ('Avg Altitude', get_avg_altitude),
                                                         ('Max Altitude', get_max_altitude),
                                                         ('Avg Speed', get_avg_speed),
                                                         ('Avg Distance From Operator', get_avg_distance_from_operator),
                                                         ('Max Distance', get_max_distance_from_operator),
                                                         ('Total Distance', get_total_distance),
                                                         ('Avg GPS Level', get_avg_gps_level),
                                                         ('Avg GPS Satellite Count', get_avg_gps_sat_count),
                                                         ('Min GPS Count', get_min_gps_sat_count),
                                                         # ("Safe Drone", get_is_safe_drone),
                                                         ('Crash Count', get_crash_count),
                                                         ('Prior to Crash Safety Score', get_safety_score_before_crash),
                                                         ('Landing Battery', get_landing_battery),
                                                         ('Low Altitude Cruise Distance', get_low_altitude_cruise_distance),
                                                         ('Avg Decline', get_avg_decline),
                                                         ('Avg Lag', get_avg_lag),
                                                         ('Max Lag', get_max_lag),
                                                         ('Avg Angle', get_avg_angle),
                                                         ('Max Angle', get_max_angle),
                                                         ('Avg Absolute Aileron', get_avg_aileron),
                                                         ('Max Absolute Aileron', get_max_aileron),
                                                         ('Avg Absolute Rudder', get_avg_rudder),
                                                         ('Max Absolute Rudder', get_max_rudder),
                                                         ('Avg Absolute Elevator', get_avg_elevator),
                                                         ('Max Absolute Elevator', get_max_elevator),
                                                         ('Avg Absolute Throttle', get_avg_throttle),
                                                         ('Max Absolute Throttle', get_max_throttle),
                                                     ],
                                                     '',
                                                     clean_file_name, overwrite_source=False)

            map_ = plotly_skylog.draw_map(lambda_input, color='green')
            graph = plotly_skylog.draw_all_graphs()
            safety_metadata = metadata_supplier.get_safety_metadata()


            result = {'map': map_, 'graph': graph, 'safety-metadata': safety_metadata,
                      'weather': '', 'filename': file_path, 'username': flight.get_meta_data()['username']}
            self.write(json.dumps(result))
        except SyntaxError as e:
            print('syntax error ' + e.message)
            raise tornado.web.HTTPError(self.BAD_LAMBDA_ERROR_CODE)
        except NameError as e:
            print('name error ' + e.message)
            raise tornado.web.HTTPError(self.BAD_LAMBDA_ERROR_CODE)
        except TypeError as e:
            print('type error ' + e.message)
            raise tornado.web.HTTPError(self.BAD_LAMBDA_ERROR_CODE)

    def post(self):
        if self.wrapper.sl is None:
            raise tornado.web.HTTPError(self.NO_SKYLOG_GIST_YET_ERROR_CODE)
        input_ = self.get_body_arguments('gistfilepath')
        if not input_:
            return None

        gist_file_path = input_[0]
        if not gist_file_path:
            return None
        self.wrapper.sl.save_gist(gist_file_path)

    def options(self):
        self.set_status(204)
        self.finish()


class SafetyScoreHandler(tornado.web.RequestHandler):

    SAFETY_DATA_MISSING = 405

    def get(self):
        file_path = self.get_query_arguments('filepath')
        try:
            data = {'safetyScoreFeedback': get_safety_score_feedback(file_path[0]), 'safetyScoreBreakdown': get_safety_score_breakdown(file_path[0])}
        except:
            raise tornado.web.HTTPError(self.SAFETY_DATA__MISSING)
        self.write(json.dumps(data))


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        # self.render('/Users/Daniel/Documents/Skywatch/skylog/web/indexLogin.html')
        self.render('/home/rmmot/skylog/web/indexLogin.html')


class LoginHandler(tornado.web.RequestHandler):

    MISSING_USER_ERROR_CODE = 400
    NO_FLIGHTS_ERROR_CODE = 401

    def get(self):
        username = self.get_query_arguments('username')
        db = mongo_source.client['flight_logs']

        if db.flights.find_one({"metadata.username": username[0]}) is None:
            raise tornado.web.HTTPError(self.MISSING_USER_ERROR_CODE)

        flights = db.flights.find({"metadata.username": username[0]}, {"metadata":1, "log_file":1, "flight_records":{"$slice":1}})

        flightArray = []
        for flight in flights:
            flightArray.append((str(flight['log_file']), get_and_convert_flightlog_time(flight)))

        if len(flightArray) == 0:
            raise tornado.web.HTTPError(self.NO_FLIGHTS_ERROR_CODE)

        sortedFlightsDictionary = sort_flights_by_datetime(flightArray)

        self.write(json.dumps(sortedFlightsDictionary))


if __name__ == "__main__":
    wrapper = SkylogWrapper()
    app = tornado.web.Application([
        (r"/skylog", MainHandler),
        (r"/skylog_request", MapHandler, dict(data=wrapper)),
        (r"/skylog_login", LoginHandler),
        (r'/web/(.*)', MyStaticFileHandler, {'path': os.path.join(os.path.dirname(__file__), 'web')}),
        (r"/skylog_safety", SafetyScoreHandler)
    ])

    app.listen(8890)
    print('skylog server ready..')
    tornado.ioloop.IOLoop.current().start()

