This is an experiment in voice over ip, not unlike mumble or ventrillo. However this project is specifically designed to use "voiceid" or another speaker recognition capability in order to quickly identify when the initially authenticated user remains that over the lifetime of the connection.

In other words, we are trying to solve the "annoying nephew" problem. This problem is identified by when a person initially logs into a P2P web service, where others generally associate a username with the actual connecting as well as maintain that way for as long as the person is authenticated with the service. In this problematic use case, the authenticated user "drops out" from the session and is replaced by another speaker (the annoying nephew) and thus begins to annoy peer users.

In order to combat this we need to provide the ability for a particular user to be "kicked" from the service, but only after the system identifies the speaker as not himself for a period of time (across the entirety of peers).


In order to use this code, python2.7, gtk3.10, pyaudio, and voiceid are all prerequisites

