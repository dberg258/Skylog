# Skylog
Drone flight-log Analyzer

This is a web-appication for viewing and analyzing DJI flight logs. 
 
skylog_dash.py contains the Tornado server which must be running in order for the web application to function. 
The html is contained in index.html and indexLogin.html

# Using the webpage:
  
  ### Option #1: No sign in
  
  * In this mode, a user does not need to sign in. Features are therefore limited. A user can input a filepath of a 
      DJI flight log and press the "Go" button. The application will then process the file and after ~2 seconds, show a 
      full report of the flight log. The left side of the screen will show a map with the drone's flight path and the 
      right side of the screen will show a table with telematics data which a user can scroll through. If the inputted 
      log file does not contain all of the telematics data, the graphs for the missing information will be blank.
 * A user can also request a random flight log, by pressing the "Load Random Flight" button. This will load a random 
      flight log from a database. 
     
 ### Option #2: Sign in
 * Press the "User Login" button located at the top right of the webpage. 
* If a correct username is inputted, a list of the users flights will be displayed. Each listed flight will be a clickable     
      link. Clicking on a flight will redirect the page to the analysis of that flight log. Additionally, safety data will be
      displayed towards the bottom. Once a flight log is loaded, a list of the users flights will still be listed at the 
      bottom.
* A user still has the option to also input a filepath.
      
    

