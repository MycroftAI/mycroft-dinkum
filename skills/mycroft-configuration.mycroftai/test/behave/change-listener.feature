Feature: Change the active wake word listening engine

  Scenario Outline: User asks to change the listener
    Given an english speaking user
     When the user says "<set the listener to something>"
     Then "mycroft-configuration" should reply with "I've set the listener to <listener>"

  Examples: set the listener requests
    | set the listener to something | listener |
    | set the listener to pocketsphinx | pocket sphinx |
    | set the listener to precise | precise |
    | change the wake word engine to pocketsphinx | pocket sphinx |
    | make it the default listener | precise |
