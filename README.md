# Introduction
Blackbaud NetCommunity provides support for [Single sign-in (SSO)](https://www.blackbaud.com/files/support/guides/bbnc/ssore.pdf)
using custom formatted hyperlinks. Since this custom scheme is neither SAML
nor OpenID Connect/OAuth 2.0, Okta does not out of the box support SSO to this application. 

However, you can still use Okta to provide SSO into Blankbaud
NetCommunity via custom implementation. 

A simple web-service that uses OpenID Connect to authenticate users forms the basis
for this custom implementation. Once the user is authenticated by Okta, the web-service
generates the custom formatted hyperlink and redirects the user to BBID. 
The diagram below shows the basic flow:

#### Sequence diagram
![SSO Service](https://user-images.githubusercontent.com/20686224/28726555-80d614f8-7376-11e7-87d7-2e3a770512be.png)


*Note: Custom hyperlink SSO implementation only applies to Blackbaud NetCommunity.
 The newer cloud product,
 [Blackbaud SKY](https://apidocs.sky.blackbaud.com/docs/authorization/) has support
 for OAuth 2.0*

# Running the sample project

`git checkout` this repository, then:

1.  `cd` to the directory you just checked out:

        $ cd flask_okta_bbid_sso
2.  Create an isolated Python environment named "venv" using [virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/):

        $ virtualenv venv
3.  Next, activate the newly created virtualenv:

        $ source venv/bin/activate
4.  Then, install the dependencies for the sample SCIM server using
    Python's ["pip" package manager](https://en.wikipedia.org/wiki/Pip_%28package_manager%29):

        $ pip install -r requirements.txt
5.  Rename **.sample.config.json** to **.okta.config.json**

        $ mv .sample.config.json .okta.config.json

6.  Edit *.okta.config.json* and provide the values for **oktaUrl**, **clientId** and **clientSecret**,
    and **sharedKey**
    
7.  Start the example service using this command:

        $ python run.py

8.  Navigate to the start homepage **http://localhost:3000/** and click on the
    button to initiate SSO into BBID NetCommunity. If you're not logged into Okta
    yet, you will first be redirected to Okta's login page. Once logged in,
    you will be redirected to BBID

## Okta Setup
Follow [these steps](https://github.com/okta/samples-python-flask/blob/master/docs/assets/oidc-app-setup.md)
to setup an OpenID Connect client in your Okta environment. There you'll find
the clientID and clientSecret values required in the run steps above.


# Appendix
## Okta Specifics and OpenID Connect Explanation
The code borrows heavily from the back-end implementation of the
[Okta samples-python-flask](https://github.com/okta/samples-python-flask)
sample project. Primarily, the **/authorization-code/callback** endpoint,
which handles the OAuth 2.0 authorization-code grant flow originated through Okta.
For an in-depth overview of the process, visit the link and follow through the README

For sample code of the same project in other languages, please
visit [this link](https://github.com/okta?utf8=%E2%9C%93&q=samples&type=&language=).
