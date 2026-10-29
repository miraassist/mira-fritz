# Testable rules of docs/spec/fritz.md. Each scenario has a fixed number (FZ-nn) that is never reused; its test
# carries the number in its name (test_FZ07_…). The tags @step1 … @step3 say in which step of the spec ("Steps") the
# scenario gets built.
#
# Groups: FZ-0x setup · FZ-1x phone book · FZ-2x messages · FZ-3x media source · FZ-4x calls

Feature: FZ Mira FRITZ!Box

  # --- Setup ----------------------------------------------------------------------------------------------

  @step1
  Scenario: FZ-01 Only user and password must be typed
    Given the config flow
    When the user types user and password
    Then the address is the FRITZ!Box's factory one
    And the entry is created after a working login

  @step1
  Scenario: FZ-02 A refused login is said in plain words
    Given a FRITZ!Box that refuses the login
    When the user sends the form
    Then the form says that user or password is wrong

  @step1
  Scenario: FZ-03 A missing right is named
    Given a FRITZ!Box user without the right for the call list
    When the user sends the form
    Then the form names the right that is missing and where to tick it

  # --- Phone book -----------------------------------------------------------------------------------------

  @step1
  Scenario: FZ-10 get_phonebook gives the chosen books
    Given a FRITZ!Box with the books "Telefonbuch" and "Google"
    And the option names only "Telefonbuch"
    When get_phonebook is called
    Then the response holds the contacts of "Telefonbuch" with their numbers, types and main number
    And the name of the book read and the box's address

  @step1
  Scenario: FZ-11 A contact in two books comes once
    Given both chosen books hold "Oma" with the same number
    When get_phonebook is called
    Then "Oma" comes once

  # --- Messages -------------------------------------------------------------------------------------------

  @step2
  Scenario: FZ-20 New messages are counted without numbers
    Given two new messages and one heard on the answering machine
    When the integration reads
    Then sensor new_messages is 2
    And its attributes name caller, date and minutes, never a number

  @step2
  Scenario: FZ-21 mark_heard marks at the box
    Given a new message
    When mark_heard is called with its id
    Then the box is told MarkMessage for it
    And sensor new_messages goes down at once

  @step2
  Scenario: FZ-22 get_messages gives what a player needs
    Given a new message from Oma
    When get_messages is called
    Then the response holds its id, the answering machine's name, name, number, date, minutes and media_content_id

  @step2
  Scenario: FZ-23 What is there at the start fires no event
    Given a message on the box when Home Assistant starts
    When the integration reads the first time
    Then no event new_message comes
    And a message after that fires one

  @step2
  Scenario: FZ-24 Deleting several goes from the highest and reads again
    Given messages 1, 2 and 3 on one answering machine
    When delete_messages is called with 1 and 3
    Then the box is told to delete 3 first, then 1 (it numbers anew after a delete)
    And the messages are read again

  @step2
  Scenario: FZ-25 Errors carry no session id
    Given the box cannot be reached on an address with the session id
    When the error is logged
    Then the session id is not in it

  # --- Media source ---------------------------------------------------------------------------------------

  @step2
  Scenario: FZ-30 A message plays without a login
    Given a message's media_content_id
    When it is resolved
    Then the URL is signed, and fetching it without a login gives the recording as WAV

  @step2
  Scenario: FZ-31 The browser lists messages newest first
    Given three messages
    When the media source is browsed
    Then they come newest first, titled with name, day, time and minutes

  # --- Calls ----------------------------------------------------------------------------------------------

  @step3
  Scenario: FZ-40 A call the answering machine took is not a missed call
    Given a call the answering machine took and one nobody took
    When the integration reads
    Then sensor missed_calls is 1
    And the one taken is a message

  @step3
  Scenario: FZ-41 mark_calls_seen sets the missed calls to zero
    Given two new missed calls
    When mark_calls_seen is called
    Then sensor missed_calls is 0
    And after a restart it stays 0

  @step3
  Scenario: FZ-42 A new missed call fires an event
    Given the integration has read once
    When a missed call from Ben comes
    Then event calls fires missed_call with name "Ben"

  # --- The call monitor ----------------------------------------------------------------------------------

  @step5
  Scenario: FZ-50 An incoming call that ended is told
    Given the call monitor sends RING, CONNECT and DISCONNECT of one call, and an outgoing call
    When the integration reads the lines
    Then only the end of the incoming call counts, and no number is kept

  @step5
  Scenario: FZ-51 The monitor reads after a call and asks only as a safety net
    Given the call monitor is there
    When an incoming call ends
    Then the box is read at once
    And asking happens every 15 minutes, every minute again once the monitor is gone

  @step5
  Scenario: FZ-52 After the answering machine it reads until the message is there
    Given the answering machine took a call (CONNECT on extension 41) and it ended
    When the box is read at once and the recording is not saved yet
    Then it is read again after 2, 3 and 5 seconds, until the new message is there
