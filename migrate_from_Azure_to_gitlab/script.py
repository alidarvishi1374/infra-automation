import json
import os
import git
from git import Repo
import subprocess


with open("repos.json") as jsonFile:
        data = json.load(jsonFile)

for key in data: 
  source = data[key]['source']
  print(type(source))
  dist = data[key]['dist']
  clone = "git clone "+source 
  os.system(clone)
  
  os.chdir(key)


  stdout = subprocess.check_output('git branch -a'.split())
  out = stdout.decode()
  branches = [b.strip('* ') for b in out.splitlines()]

  for branch in branches:
    if not branch == 'master':
      branch_new = branch.replace("remotes/origin/","")
      if branch_new not in ('master','HEAD -> origin/master'):
        print(branch_new)
        git_checkout = "git switch "+branch_new
        os.system(git_checkout)

  os.chdir(".git")

  with open(r'config', 'r') as file:
    data_2 = file.read()
    data_2 = data_2.replace(source, dist)
  with open(r'config', 'w') as file:
    file.write(data_2)
  os.system("git push origin --all --force")
  os.chdir("/home")

