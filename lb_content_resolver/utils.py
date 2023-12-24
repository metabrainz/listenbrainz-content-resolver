def ask_yes_no_question(prompt):

    while True:
        resp = input(prompt)
        resp = resp.strip()
        if resp == "":
            resp = 'y'

        if resp == 'y':
            return True
        elif resp == 'n':
            return False
        else:
            print("eh? try again.")
