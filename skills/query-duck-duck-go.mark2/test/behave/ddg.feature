Feature: DuckDuckGo Skill

  Scenario Outline: user asks a question about a person
    Given an english speaking user
     When the user says "<tell me about a person>"
     Then "skill-ddg" should reply with anything
     And mycroft reply should contain "<person>"
     Then dialog is stopped

  Examples: user asks a question about a person
    | tell me about a person | person |
    | ask duckduckgo who is the president of the united states | president |
    | ask ducky who was abraham lincoln | lincoln |
    | ask the duck who were the beatles | beatles |
    | ask duckduckgo who is queen elizabeth | queen |
    | what does the duck have to say about al capone | capone |
    | ask the duck what is the secretary general of the united nations | secretary |
    | duckduckgo who is the secretary general of the united nations | secretary |
    | ask duckduckgo about George Church | church |

  Scenario Outline: user asks a question about a place
    Given an english speaking user
     When the user says "<tell me about a place>"
     Then "skill-ddg" should reply with anything
     And mycroft reply should contain "<place>"
     Then dialog is stopped

  Examples: user asks a question about a place
    | tell me about a place | place |
    | ask duckduckgo about amsterdam | amsterdam |
    | ask duckduckgo about tokyo | japan |
    | ask duckduckgo about the north pole | pole |

  Scenario Outline: user asks a question about a thing
    Given an english speaking user
     When the user says "<tell me about a thing>"
     Then "skill-ddg" should reply with anything
     And mycroft reply should contain "<thing>"
     Then dialog is stopped

  Examples: user asks a question about a thing
    | tell me about a thing | thing |
    | ask duckduckgo what is a sandwich | sandwich |
    | whats the duck say about sandwiches | sandwich |
    | ask duckduckgo about hammers | hammer |
    | ask duckduckgo what is an automobile | car |
    | ask ducky what is a car | car |
    | what does duckduckgo say about failures | failure |

  Scenario Outline: user asks a question about an idea
    Given an english speaking user
     When the user says "<tell me about an idea>"
     Then "skill-ddg" should reply with anything
     And mycroft reply should contain "<idea>"
     Then dialog is stopped

  Examples: user asks a question about an idea
    | tell me about an idea | idea |
    | ask duckduckgo about philosophy | philosophy |
    | ask the duck what is politics | politics |
    | what does the duck say about science | knowledge |

