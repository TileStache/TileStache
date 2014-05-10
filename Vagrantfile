# -*- mode: ruby -*-
# vi: set ft=ruby :

VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  config.vm.box = "Trusty64Daily"
  config.vm.box_url = "http://cloud-images.ubuntu.com/vagrant/trusty/20140501/trusty-server-cloudimg-amd64-vagrant-disk1.box"

  #config.vm.network :private_network, ip: "192.168.33.10"

  config.vm.synced_folder ".", "/srv/tilestache"

  config.vm.provision :shell, :privileged => false, :inline => "sh /srv/tilestache/Vagrant/setup.sh"

end
