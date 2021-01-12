# NSO Service with Restore Points Stored in Git

A simple example on how to add restore points to your NSO services. Each restore point will be exported to a local Git repository where a new branch will be created for each service instance. Each restore point contains a full copy of your service instance at that moment.

So why wouldnt you just use the NSO rollback files? Well for one thing it might be hard to find the right rollback, and how many rollback files to you keep? And also remember that each rollback only has the change you made in that commit so to fully restore it you have to do a cummulative rollback.

My example works as a stacked service, adding a layer on top of the service-provider MPLS example (examples.ncs/service-provider/mpls-vpn), but you can easily just add the code to your own service.

I've tried to make it at least somewhat generic so that it should be fairly easy to adapt to your service.

First at each service commit, the post_modification copies the service config to what we can call a shadow copy of the service, its just a copy of the service YANG in a different list, it is from here a subscriber saves the service to Git. The reason for the shadow tree is that I didnt want to run the git commands from the service post_modification and if the save action would be executed from a kicker or subscriber we couldnt guarantee that we would catch all commits. There might be two quick consecutive commits and the kicker might not be quick enough to execute in between.

So, once in the shadow tree there is a subscriber that listens to all changes and executes the save action. The save action saves the commit to Git and also deletes the entry from the shadow tree. So why a subscriber and not a kicker? Kickers will kick even if the change is a delete and its hard (impossible?) to handle when the kicker monitors broadly and not on a specific leaf.

To restore a service there is a data provider that lists the commits for each branch and a corresponding restore action.

### Install

```
cp -r top-l3vpn examples.ncs/service-provider/mpls-vpn/packages
cd examples.ncs/service-provider/mpls-vpn
make all
cd packages/top-l3vpn/src/
make
cd -
make start
```

Create a folder for the local git repository
```
mkdir l3vpn-git
```

Point you service to the repository folder, if you didnt already initialize a git repo setting the path here will do it for you.
```
ncs_cli -u admin
admin@ncs% set git repository-path /Users/hniska/ncs-release/5.3.2/examples.ncs/service-provider/mpls-vpn/l3vpn-git
commit
```

### Demo

Create your service instance

```
ncs_cli -u admin
configure
set top-l3vpn Ikea route-distinguisher 456
set top-l3vpn Ikea endpoint branch-office1 ce-device ce0
set top-l3vpn Ikea endpoint branch-office1 ce-interface GigabitEthernet0/11
set top-l3vpn Ikea endpoint branch-office1 ip-network 10.7.7.0/24
set top-l3vpn Ikea endpoint branch-office1 bandwidth 6000000
set top-l3vpn Ikea endpoint branch-office1 as-number 65102
set top-l3vpn Ikea endpoint branch-office2 ce-device ce4
set top-l3vpn Ikea endpoint branch-office2 ce-interface GigabitEthernet0/18
set top-l3vpn Ikea endpoint branch-office2 ip-network 10.8.8.0/24
set top-l3vpn Ikea endpoint branch-office2 bandwidth 300000
set top-l3vpn Ikea endpoint branch-office2 as-number 65103
set top-l3vpn Ikea endpoint main-office ce-device ce6
set top-l3vpn Ikea endpoint main-office ce-interface GigabitEthernet0/11
set top-l3vpn Ikea endpoint main-office ip-network 10.10.1.0/24
set top-l3vpn Ikea endpoint main-office bandwidth 12000000
set top-l3vpn Ikea endpoint main-office as-number 65101
```
Lets take a look at what it would commit, Ive cut away all the device config data and you can see that in this example it creates
* top-l3vpn instance called Ikea
* restore point named Ikea - timestamp (Ikea-2020-06-03_14:58:09) under l3vpn-restore-points
* sub service under vpn l3vpn Ikea that does the actual device configuration

The device configuration could of course be done in the top-l3vpn instance and then scrapping the sub service.

```
admin@ncs% commit dry-run
cli {
    local-node {
        data
...
...
...
             +top-l3vpn Ikea {
             +    route-distinguisher 456;
             +    endpoint branch-office1 {
             +        ce-device ce0;
             +        ce-interface GigabitEthernet0/11;
             +        ip-network 10.7.7.0/24;
             +        bandwidth 6000000;
             +        as-number 65102;
             +    }
             +    endpoint branch-office2 {
             +        ce-device ce4;
             +        ce-interface GigabitEthernet0/18;
             +        ip-network 10.8.8.0/24;
             +        bandwidth 300000;
             +        as-number 65103;
             +    }
             +    endpoint main-office {
             +        ce-device ce6;
             +        ce-interface GigabitEthernet0/11;
             +        ip-network 10.10.1.0/24;
             +        bandwidth 12000000;
             +        as-number 65101;
             +    }
             +}
             +l3vpn-restore-points Ikea-2020-06-10_14:42:52 {
             +    route-distinguisher 456;
             +    endpoint branch-office1 {
             +        ce-device ce0;
             +        ce-interface GigabitEthernet0/11;
             +        ip-network 10.7.7.0/24;
             +        bandwidth 6000000;
             +        as-number 65102;
             +    }
             +    endpoint branch-office2 {
             +        ce-device ce4;
             +        ce-interface GigabitEthernet0/18;
             +        ip-network 10.8.8.0/24;
             +        bandwidth 300000;
             +        as-number 65103;
             +    }
             +    endpoint main-office {
             +        ce-device ce6;
             +        ce-interface GigabitEthernet0/11;
             +        ip-network 10.10.1.0/24;
             +        bandwidth 12000000;
             +        as-number 65101;
             +    }
             +}
              vpn {
             +    l3vpn Ikea {
             +        route-distinguisher 456;
             +        endpoint branch-office1 {
             +            ce-device ce0;
             +            ce-interface GigabitEthernet0/11;
             +            ip-network 10.7.7.0/24;
             +            bandwidth 6000000;
             +            as-number 65102;
             +        }
             +        endpoint branch-office2 {
             +            ce-device ce4;
             +            ce-interface GigabitEthernet0/18;
             +            ip-network 10.8.8.0/24;
             +            bandwidth 300000;
             +            as-number 65103;
             +        }
             +        endpoint main-office {
             +            ce-device ce6;
             +            ce-interface GigabitEthernet0/11;
             +            ip-network 10.10.1.0/24;
             +            bandwidth 12000000;
             +            as-number 65101;
             +        }
             +    }
              }
    }
}
```

Heres a look at the restore point, as you can see its just a full copy of the last commit, well you will probably not be quick enough to see it as the subscriber already ran save on the restore point and after the data has been commited to git it gets deleted from NSO.

```
admin@ncs% show l3vpn-restore-points
l3vpn-restore-points Ikea-2020-06-10_14:42:52 {
    route-distinguisher 456;
    endpoint branch-office1 {
        ce-device    ce0;
        ce-interface GigabitEthernet0/11;
        ip-network   10.7.7.0/24;
        bandwidth    6000000;
        as-number    65102;
    }
    endpoint branch-office2 {
        ce-device    ce4;
        ce-interface GigabitEthernet0/18;
        ip-network   10.8.8.0/24;
        bandwidth    300000;
        as-number    65103;
    }
    endpoint main-office {
        ce-device    ce6;
        ce-interface GigabitEthernet0/11;
        ip-network   10.10.1.0/24;
        bandwidth    12000000;
        as-number    65101;
    }
}
```
The subscriber executes this
```
admin@ncs% request l3vpn-restore-points Ikea-2020-06-10_14:42:52 save
```

Let see the thing in action then, lets delete one of the vpn endpoints

```
admin@ncs% delete top-l3vpn Ikea endpoint branch-office1
[ok][2020-06-03 15:00:09]

[edit]
admin@ncs% show | compare
 top-l3vpn Ikea {
-    endpoint branch-office1 {
-        ce-device ce0;
-        ce-interface GigabitEthernet0/11;
-        ip-network 10.7.7.0/24;
-        bandwidth 6000000;
-        as-number 65102;
-    }
 }
admin@ncs% commit
Commit complete.
[ok][2020-06-03 15:00:17]
```

Lets take a look at the restore points
```
admin@ncs% run show top-l3vpn Ikea restore-points
COMMIT                                    TIME
--------------------------------------------------------------------
72911f99c6772de062fa2c6271ebf93000b16d6a  Ikea-2020-06-09_10:11:42
8dcbc3b1b9d69e33b8a44da464507cd9915f1d38  Ikea-2020-06-10_14:43:39
fa26dbe77d7716ab4c1f9af7da6ada93efdfc8a5  Ikea-2020-06-10_14:46:02

[ok][2020-06-10 14:46:58]
```

So lets take a look at that next to last restore point

```
admin@ncs% request top-l3vpn Ikea restore-points restore-point 8dcbc3b1b9d69e33b8a44da464507cd9915f1d38 show
result
<config xmlns="http://tail-f.com/ns/config/1.0">
  <l3vpn-restore-points xmlns="http://example.com/top-l3vpn">
    <name>Ikea-2020-06-10_14:43:39</name>
    <route-distinguisher>456</route-distinguisher>
    <endpoint>
      <id>branch-office1</id>
      <ce-device>ce0</ce-device>
      <ce-interface>GigabitEthernet0/11</ce-interface>
      <ip-network>10.7.7.0/24</ip-network>
      <bandwidth>6000000</bandwidth>
      <as-number>65102</as-number>
    </endpoint>
    <endpoint>
      <id>branch-office2</id>
      <ce-device>ce4</ce-device>
      <ce-interface>GigabitEthernet0/18</ce-interface>
      <ip-network>10.8.8.0/24</ip-network>
      <bandwidth>300000</bandwidth>
      <as-number>65103</as-number>
    </endpoint>
    <endpoint>
      <id>main-office</id>
      <ce-device>ce6</ce-device>
      <ce-interface>GigabitEthernet0/11</ce-interface>
      <ip-network>10.10.1.0/24</ip-network>
      <bandwidth>12000000</bandwidth>
      <as-number>65101</as-number>
    </endpoint>
  </l3vpn-restore-points>
</config>
```

Looks fine, lets restore it and see what changes that would do
```

admin@ncs% request top-l3vpn Ikea restore-points restore-point 8dcbc3b1b9d69e33b8a44da464507cd9915f1d38 restore
[ok][2020-06-10 14:48:39]

[edit]
admin@ncs% show | compare
 top-l3vpn Ikea {
+    endpoint branch-office1 {
+        ce-device ce0;
+        ce-interface GigabitEthernet0/11;
+        ip-network 10.7.7.0/24;
+        bandwidth 6000000;
+        as-number 65102;
+    }
 }
[ok][2020-06-10 14:48:44]

[edit]
admin@ncs%
```

### Contact

Contact Hakan Niska <hniska@cisco.com> with any suggestions or comments. If you find any bugs please fix them and send me a pull request.

