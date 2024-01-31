# DevinProjects
<!-- ABOUT THE PROJECT -->
## About The Project

[![Devin's Backgammon Game][product-screenshot]](https://www.flickr.com/photos/199587573@N06/53344540746/in/dateposted-public/lightbox/)

This is a fully functional, tournament style Backgammon game in which two clients can connect and play.
Complete with flawless forced move detection and a simple, yet appealing interface, this is one of the best ways to play online backgammon.
Any backgammon fan could appreciate playing this one and is simple and inviting enough for newbies!
The newest addition to this project is a computer player the user can play against.
This project is written in Python.

### Built With
This project uses a GUI framework known as Tkinter, which is built-in to Python and compatiable with all major operating systems.
* [Python](https://python.org)


<!-- GETTING STARTED -->
## Getting Started

You can easily see how this project works by starting the server script and subsequently starting the client applications, all from the command line.
These files implement the server to work as a local host, but this can easily be changed by hardcoding an IP address into server and socket instantiations.
Only one third-party Python module is used (screeninfo), which is can easily be added to newer Python installations.

This project assumes the client has Python on their machine and can use 'pip' calls to download official third-party modules.
As of right now, the server script really just represents a 'room' i.e. two players playing one session.  As this project grows, these 'rooms' could be the building blocks for a full-scale backgammon service.

### Installation

1. Make sure Python is installed on your machine.
   
2. Download screeninfo module (if not already downloaded) by typing in the following on the command line:
```sh
pip screeninfo
```
   You will be notified of a successful installation.

3. Place all four of my python files(client application, board module, computer player, and server application) in a directory that Python recognizes, and run server and subsequent clients as scripts on the command line.



<!-- ROADMAP -->
## Roadmap

This project strives to be an enjoyable experience for veteran and new backgammon players alike.  Clicking any piece when it is your turn will
show every possibly place that piece can move with the current dice data, and a simple right-click anywhere on the board will undo the previous move.
If a move is "forced", meaning there is only one way to perform a move with a certain roll, the 'Do Forced Move' button will enable itself and the client
must click this button to proceed.  I'm confident this forced move detection algorithm will detect every possible scenario in which a move is forced.
Another noteworthy feature is the pip-counter, which always stays updated with pip-counts for both players.

A new addition to this game is the "gammonAI.py" file.  The client composes itself with either a ComputerPlayer or Socket object which represents a one-player
and online experience, respectively.  Much like the server, a ComputerPlayer object coordinates the events of the game and contains all the logic for it's moves.

Potential issues in developing this project could arise if upscaling for general public to use, due to the possible redesigns in how the server system works,
however, the game handlers within the server would not need changing (the threads which control the flow of the game.) 


<!-- CONTACT -->
## Contact

Devin Fowler - devin.fowler.lu@gmail.com - 1-(618)-980-5201

Project Link: [https://github.com/pythondevin/DevinProjects](https://github.com/pythondevin/DevinProjects)

Feel free to contact me with questions, concerns, or whatever!


<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[build-shield]: https://img.shields.io/badge/build-passing-brightgreen.svg?style=flat-square
[build-url]: #
[contributors-shield]: https://img.shields.io/github/contributors/othneildrew/Best-README-Template.svg?style=flat-square
[contributors-url]: https://github.com/othneildrew/Best-README-Template/graphs/contributors
[license-shield]: https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square
[license-url]: https://github.com/othneildrew/Best-README-Template/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=flat-square&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/othneildrew
[product-screenshot]: images/screenshot.png
