Feature: Wikipedia Skill

  Scenario Outline: user asks a question about a person
    Given an english speaking user
     When the user says "<tell me about a person>"
     And mycroft reply should contain "<person>"
     Then dialog is stopped

  Examples: user asks a question about a person
    | tell me about a person | person |
    | ask wiki who was abraham lincoln | lincoln |
    | tell me about abraham lincoln | lincoln |
    | what does wiki say about nelson mandela | mandela |
    | ask wiki who is queen elizabeth | elizabeth |
    | ask wikipedia who was Mahatma Gandhi | gandhi |
    | tell me about the president of the united states | president |
    | ask wikipedia who is the secretary general of the united nations | secretary |
    | ask wiki who is the president of the united states | president |
    | tell me about the secretary general of the united nations | secretary |

  Scenario Outline: trigger a disambiguate response
    Given an english speaking user
     When the user says "<tell me about a person>"
     And mycroft reply should contain "<person>"
     Then dialog is stopped

  Examples: user asks a question about a person
    | tell me about a person | person |
    | tell me about George Church | church |

  Scenario Outline: user asks a question about a place
    Given an english speaking user
     When the user says "<tell me about a place>"
     And mycroft reply should contain "<place>"
     Then dialog is stopped

  Examples: user asks a question about a place
    | tell me about a place | place |
    | ask wikipedia where is amsterdam | netherlands |
    | tell me about tokyo | japan |
    | ask wiki where is the grand canyon | arizona |
    | what does wiki know about pikes peak | peak |
    | ask wiki where is the nile river | africa |

  Scenario Outline: user asks a question about something
    Given an english speaking user
     When the user says "<tell me about a thing>"
     And mycroft reply should contain "<thing>"
     Then dialog is stopped

  Examples: user asks a question about a thing
    | tell me about a thing | thing |
    | tell me about sandwiches | sandwich |
    | tell me about hammers | hammer |
    | ask wiki what is a chain saw | saw |
    | what does wiki know about the universe | universe |
    | tell me about automobiles | car |

  Scenario Outline: user asks a question about an idea
    Given an english speaking user
     When the user says "<tell me about an idea>"
     And mycroft reply should contain "<idea>"
     Then dialog is stopped

  Examples: user asks a question about an idea
    | tell me about an idea | idea |
    | tell me about philosophy | philosophy |
    | tell me about politics | politics |
    | tell me about science | knowledge |
    | ask wiki what is mathematics | mathematics |
