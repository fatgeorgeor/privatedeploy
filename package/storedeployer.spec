%global debug_package %{nil}
%global __strip /bin/true

Name:           storedeployer
Version:        %{ver}
Release:        %{rel}%{?dist}

Summary:	storedeployer

Group:		SDS
License:	GPL
URL:		http://github.com/journeymidnight
Source0:	%{name}-%{version}-%{rel}.tar.gz
BuildRoot:	%(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)

%description


%prep
%setup -q -n %{name}-%{version}-%{rel}

%build

%install
mkdir -p  %{buildroot}/binaries/storedeployer
cp -r *   %{buildroot}/binaries/storedeployer/

#ceph confs ?

%post


%preun

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
/binaries/storedeployer/*

%changelog
