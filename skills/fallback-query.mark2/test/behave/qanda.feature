Feature: Question and Answer functionality

  Scenario Outline: user asks who someone is
    Given an english speaking user
     When the user says "<who is a person>"
     Then mycroft reply should contain "<person>"

  Examples: who questions
    | who is a person | person |
    | who is george church | church |
    | who are the foo fighters | foo |
    | who built the eiffel tower | sauvestre |
    | who wrote the book outliers | gladwell |
    | who discovered helium | janssen |

  Scenario Outline: user asks a what question
    Given an english speaking user
     When the user says "<what is a thing>"
     Then mycroft reply should contain "<thing>"

  Examples: what questions
    | what is a thing | thing |
    | what is metallurgy | metallurgy |
    | what is the melting point of aluminum | 660 |

  Scenario Outline: user asks when something is
    Given an english speaking user
     When the user says "<when did this happen>"
     Then mycroft reply should contain "<time>"

  Examples: when questions
    | when did this happen | time |
    | when was the last ice age | ice age |
    | when will the sun die | billion |

  Scenario Outline: user asks where something is
   Given an english speaking user
    When the user says "<where is a place>"
    Then mycroft reply should contain "<place>"

  Examples: what questions
    | where is a place | place |
    | where is morocco | africa |
    | where is saturn | saturn |
    | where is the smithsonian | washington |

  Scenario Outline: user asks a how question
    Given an english speaking user
      And the user's unit system is imperial
     When the user says "<how is this a thing>"
     Then mycroft reply should contain "<the answer>"

  Examples: what questions
    | how is this a thing | the answer |
    | how tall is the eiffel tower | 1083 |
    | what is the distance to the moon | distance |
    | how far is it from vienna to berlin | vienna |

  @xfail
  Scenario Outline: user asks a question mycroft can't answer
    Given an english speaking user
     When the user says "<failing query>"
     Then mycroft reply should contain "<expected answer>"

  Examples: what questions
    | failing query | expected answer |
    | what is a timer | interval |
    | what is the drinking age in canada | 19 |
    | how hot is the sun | sun |
    | when was alexander the great born | 356 |
