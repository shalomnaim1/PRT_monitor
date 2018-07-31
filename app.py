#!/bin/python

from flask import Flask, render_template,redirect, url_for
import requests
from flask import request
from threading import Thread
from time import sleep
import os.path
import atexit

app = Flask(__name__)

pr_list_file = "pr_list.txt"
PR_STAT_URL = "http://10.16.4.32/trackerbot/api/pr/{id}/"
PRT_LINK = "http://10.16.4.32/trackerbot/pr/pr/{id}"
STEEP_TIME = 30

class pr(object):

    def __init__(self, id, title="Unknown", state="Unknown"):
        self.id = id
        self.title = title
        self.state = state

        print "PR Created: {pr}".format(pr=self)

    def __str__(self):
        return "ID:{id} TITLE:{title} STATE:{state}".format(**self.__dict__)

    def update(self):
        rc = True
        try:
            res = requests.get(PR_STAT_URL.format(id=self.id))

            if res.status_code == 200:
                res = res.json()
                self.id = res["number"]
                self.title = res["title"]
                if res["runs"]:
                    self.state = res["runs"][0]["result"]
                else:
                    self.state = "Never ran in PRT yet..."
            else:
                print "Request failed for PR #{id}".format(id=self.id)
                print res
                rc = False
        except Exception as ex:
            print ex.message
            print
            print res
            rc = False
        finally:
            return rc

    @property
    def link(self):
        return PRT_LINK.format(id=self.id)

class prs_monitor(object):
    def __init__(self, pr_list_file):
        self.load_pr_list(pr_list_file)
        self.keep_running = True
        self.update_threads = []
        self.update_pr_statuses()


        self.update_state = Thread(target=self.update)
        self.update_state.daemon = True
        self.update_state.start()

    def load_pr_list(self,path):
        if os.path.isfile(path):
            with open(path, 'r+') as f:
                self.prs = [pr(int(pr_id)) for pr_id in f.readlines()]
        else:
            self.prs =[]

    def dump_prs(self):
        print "Dumpping..."
        ids = ["{id}\n".format(id=pr.id) for pr in self.prs]

        with open(pr_list_file, 'w') as f:
            f.writelines(ids)

    def update_pr_statuses(self):
        for pr in self.prs:
            t = Thread(target=pr.update)
            t.daemon = True
            self.update_threads.append(t)
            t.start()

    def update(self):
        time_passed = 0
        while self.keep_running:
            if time_passed <= STEEP_TIME:
                print "DEBUG: Updating statuses"
                self.update_pr_statuses()
                map(lambda t:t.join, self.update_threads)
                self.update_threads = []
                time_passed = 0
                time_passed += 5

            sleep(5)

    def add_pr(self, id):
        if id not in [_pr.id for _pr in self.prs]:
            new_pr = pr(id)
            new_pr.update()

            self.prs.append(new_pr)

    def remove_pr(self, id):
        self.prs = [pr for pr in self.prs if pr.id != int(id)]

monitor_instance = prs_monitor(pr_list_file)

def teardown():
    monitor_instance.keep_running = False
    monitor_instance.dump_prs()
    monitor_instance.update_state.join()


@app.route('/')
def show_deshboard():
    return render_template("main.html", prs=monitor_instance.prs)

@app.route('/change')
def change_pr():
    action = request.args.get("action")
    id = int(request.args.get("id"))

    actions = {"add": monitor_instance.add_pr, "remove": monitor_instance.remove_pr}

    actions[action](id)

    return redirect(url_for("show_deshboard"))

if __name__ == '__main__':
    atexit.register(teardown)
    app.run()
