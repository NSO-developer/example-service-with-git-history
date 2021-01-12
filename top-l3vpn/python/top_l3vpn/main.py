# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.application import Service
from datetime import datetime
import ncs.maagic as maagic
from ncs.dp import Action
import _ncs
import ncs.experimental
from git import Repo
import git
from pydriller import RepositoryMining
import socket
import os.path


def branch_exists(branch, repo):
    repo_heads = repo.heads
    if branch in [h.name for h in repo_heads]:
        return True
    else:
        return False


def create_branch(branch, repo):
    repo.git.checkout('-b', branch)


def checkout_branch(branch, repo):
    repo.git.checkout(branch)


def show_file(repo, hash, file):
    return repo.git.show("%s:%s" % (hash, file))


def get_commit_msg(repo, hash):
    return repo.git.log('-1', '--pretty=format:%s', hash)


def is_git_repo(path):
    try:
        _ = Repo(path).git_dir
        return True
    except git.exc.InvalidGitRepositoryError:
        return False


def save_to_git(trans, path_and_file, kp):
    m = ncs.maapi.Maapi()
    id = trans.save_config(m.CONFIG_XML_PRETTY, str(kp))
    with open(path_and_file, "w+") as service_file:
        try:
            s = socket.socket()
            _ncs.stream_connect(s, id, 0, ip='127.0.0.1', port=_ncs.NCS_PORT)
            data = ''
            while True:
                config_data = s.recv(4096)
                if not config_data:
                    break
                service_file.write(config_data.decode('utf-8'))
                data += str(config_data)
            return data
        finally:
            s.close()


class RestoreFromGitAction(Action):
    @Action.action
    def cb_action(self, uinfo, name, kp, input, output, trans):
        self.log.info('action name: ', name)
        self.log.info('kp: ', str(kp))
        root = ncs.maagic.get_root(trans)
        restore_point = ncs.maagic.get_node(trans, kp, shared=False)
        service = restore_point._parent._parent._parent
        branch = restore_point._parent._parent._parent.name
        repo_path = root.top_l3vpn__git.repository_path
        repo = Repo(repo_path)

        xml = show_file(repo, str(restore_point.commit), branch + '.txt')
        m = ncs.maapi.Maapi()
        self.log.info('Config: ', xml)
        trans.load_config_cmds(m.CONFIG_XML | m.CONFIG_REPLACE, xml, path=restore_point._path)
        # Full shadow restore point name can be found in the commit message
        shadow_rp_name = get_commit_msg(repo, restore_point.commit)
        rp = root.top_l3vpn__l3vpn_restore_points[shadow_rp_name]
        del service._parent[service.name]
        trans.copy_tree(rp._path, service._path)
        del rp._parent[rp.name]


class ShowFromGitAction(Action):
    @Action.action
    def cb_action(self, uinfo, name, kp, input, output, trans):
        self.log.info('action name: ', name)
        self.log.info('kp: ', str(kp))
        root = ncs.maagic.get_root(trans)
        restore_point = ncs.maagic.get_node(trans, kp, shared=False)
        branch = restore_point._parent._parent._parent.name
        repo_path = root.top_l3vpn__git.repository_path
        repo = Repo(repo_path)

        output.result = '\n' + show_file(repo, str(restore_point.commit), branch + '.txt')


class SaveAction(Action):
    @Action.action
    def cb_action(self, uinfo, name, kp, input, output, trans):
        self.log.info('action name: ', name)
        result = ''
        with ncs.maapi.Maapi() as m:
            with m.start_write_trans(usid=uinfo.usid) as t:
                root = ncs.maagic.get_root(t)
                restore_point = ncs.maagic.get_node(t, kp, shared=False)
                # We know the restore point name follows this format
                # Ikea-2020-06-03_15:01:54
                # So we can safely cut from the third - from right
                branch = restore_point.name.rsplit('-', 3)[0]
                if is_git_repo(root.top_l3vpn__git.repository_path):
                    repo_path = root.top_l3vpn__git.repository_path
                    file_name = branch + '.txt'
                    path_and_file = repo_path + '/' + file_name
                    repo = Repo(repo_path)

                    if branch_exists(branch, repo):
                        checkout_branch(branch, repo)
                    else:
                        create_branch(branch, repo)
                        self.log.info('created new branch ', branch)

                    save_to_git(t, path_and_file, kp)
                    repo.index.add(file_name)
                    result = repo.index.commit(restore_point.name)
                    del restore_point._parent[restore_point.name]
                    t.apply()
                else:
                    result = 'No GIT repository set under /git/repository-path'
        output.result = str(result)


class ServiceCallbacks(Service):
    @Service.create
    def cb_create(self, tctx, root, service, proplist):

        self.log.info('path: ' + service._path)
        vars = ncs.template.Variables()
        template = ncs.template.Template(service)
        template.apply('top-l3vpn-template', vars)

    @Service.post_modification
    def cb_post_modification(self, tctx, op, kp, root, proplist):
        self.log.info('Service postmod(service=', kp, ')')
        self.log.info('Service postmod(op=', str(op), ')')
        """
        OP = 1: 'CREATED', 2: 'DELETED', 3: 'MODIFIED', 4: 'VALUE_SET', 5: 'MOVED_AFTER', 6: 'ATTR_SET'
        """
        if op != 2:
            service = maagic.get_node(maagic.get_trans(root), kp)
            restore_point = root.top_l3vpn__l3vpn_restore_points.create(service.name + '-' + datetime.now().strftime("%Y-%m-%d_%H:%M:%S"))
            t = maagic.get_trans(root)
            t.copy_tree(service._path, restore_point._path)


class GitServiceCallbacks(Service):
    @Service.create
    def cb_create(self, tctx, root, service, proplist):
        self.log.info('path: ' + service._path)
        if os.path.isdir(service.repository_path):
            if not is_git_repo(service.repository_path):
                Repo.init(service.repository_path)
                self.log.info('GIT repository initialized at ' + service.repository_path)
        else:
            raise Exception('Repository path ' + service.repository_path + ' does not exist')


class RestorePointHandler(object):
    def __init__(self):
        # Cache the interface list
        print('RestorePointHandler init')
        self.cache = {}

    def get_data(self, tctx, branch):
        print("RestorePointHandler get new data from branch: " + str(branch))
        # Check if the interface list is already in the cache, if not populate it
        # I do this so I dont have to keep track of where we are in the list
        username = tctx.uinfo.username
        context = tctx.uinfo.context
        if branch not in self.cache:
            with ncs.maapi.single_read_trans(username, context) as trans:
                root = ncs.maagic.get_root(trans)
                repo_path = root.top_l3vpn__git.repository_path
                repo = Repo(repo_path)

                if not repo.bare:
                    commits = []
                    for commit in RepositoryMining(repo_path, filepath=str(branch) + ".txt").traverse_commits():
                        commits.append({'commit': str(commit.hash),
                                        'time': str(commit.msg)})

                    self.cache[branch] = commits
                    return commits
        else:
            return self.cache[branch]

    def get_object(self, tctx, kp, args):
        print('RestorePointHandler get object kp: ' + str(kp) + ' args: ' + str(args))
        commit = next((o for o in self.get_data(tctx, args['top-l3vpn'])
                       if o['commit'] == args['restore-point']), None)

        # Clear cache
        self.cache.pop(args['top-l3vpn'])
        return commit

    def get_next(self, tctx, kp, args, next):
        print("RestorePointHandler get next kp: " + str(kp) + ' args: ' + str(args) + ' next: ' + str(next))
        data = self.get_data(tctx, args['top-l3vpn'])
        if not data:
            return None
        if next >= len(data):
            # just clearing the cache so that the next connection gets new data.
            # dont want to keep track of the next counter
            self.cache.pop(args['top-l3vpn'])
            return None
        return data[next]

    def count(self, tctx, kp, args):
        if self.get_data(args['top-l3vpn']):
            return len(self.get_data(args['top-l3vpn']))
        else:
            return 0


# ------------------------------------------------
# SUBSCRIBER for deletes, only here until kickers can distinguish between create/delete
# ------------------------------------------------
class SaveSubscriber(ncs.cdb.Subscriber):
    def init(self):
        self.register('/top-l3vpn:l3vpn-restore-points', priority=100)

    # Initate your local state
    def pre_iterate(self):
        return []

    # Iterate over the change set
    def iterate(self, keypath, op, oldval, newval, state):
        self.log.info('SaveSubscriber kp: ' + str(keypath))
        # 2: 'MOP_DELETED'
        if op != 2:
            response_kp = str(keypath)
            state.append(response_kp)
        return ncs.ITER_RECURSE

    # This will run in a separate thread to avoid a transaction deadlock
    def post_iterate(self, state):
        self.log.info('SaveSubscriber: post_iterate, state=', state)
        with ncs.maapi.single_read_trans('system', 'system') as trans:
            # we only need the first entry that points to the restore point
            restore_point = ncs.maagic.get_node(trans, state[0])
            restore_point.top_l3vpn__save()
            self.log.info('Executed the save action on restore point ', restore_point.name)

    # determine if post_iterate() should run
    def should_post_iterate(self, state):
        return state != []


# ---------------------------------------------
# COMPONENT THREAD THAT WILL BE STARTED BY NCS.
# ---------------------------------------------
class Main(ncs.application.Application):
    def setup(self):
        self.log.info('Main RUNNING')
        self.register_service('top-l3vpn-servicepoint', ServiceCallbacks)
        self.register_service('git-servicepoint', GitServiceCallbacks)

        self.register_action('save-action', SaveAction)
        self.register_action('restore-from-git-action', RestoreFromGitAction)
        self.register_action('show-from-git-action', ShowFromGitAction)

        def start_dcb_fun(state):
            self.log.info('registering callback for git commits')
            dcb = ncs.experimental.DataCallbacks(self.log)
            dcb.register("/top-l3vpn:top-l3vpn/top-l3vpn:restore-points/top-l3vpn:restore-point", RestorePointHandler())
            _ncs.dp.register_data_cb(state['ctx'], "git-restore-points", dcb)
            return dcb

        def stop_dcb_fun(dcb):
            pass

        self.register_fun(start_dcb_fun, stop_dcb_fun)

        # Create your subscriber
        self.sub = SaveSubscriber(app=self)
        self.sub.start()

    def teardown(self):
        self.sub.stop()
        self.log.info('Main FINISHED')
