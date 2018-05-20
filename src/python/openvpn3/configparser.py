#  OpenVPN 3 Linux client -- Next generation OpenVPN client
#
#  Copyright (C) 2017 - 2018  OpenVPN Inc. <sales@openvpn.net>
#  Copyright (C) 2017 - 2018  David Sommerseth <davids@openvpn.net>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, version 3 of the
#  License.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

##
# @file  configparser.py
#
# @brief  Parses OpenVPN command line options and configuration files
#

import argparse
import os
import shlex

# Detect if pyOpenSSL is available or not.
# This module is used to parse PKCS#12 files only
# and if not present when needed, it will complain
# later on.
HAVE_OPENSSL = True
try:
    import OpenSSL.crypto as crypto
except ImportError:
    HAVE_OPENSSL = False


##
#  Configuration parser for OpenVPN command line options and configuration
#  files.  This implementation only adds the client related options the
#  OpenVPN 3 Core library supports.  Some options are ignored, as it is
#  possible to establish a connection even though the core library does not
#  use them.
#
#  This parser is also trying to behave as close as possible
#  to the classic OpenVPN 2.x
#
#
class ConfigParser():
    def __init__(self, args, descr):
        self.__args = args[1:]
        self.__parser = argparse.ArgumentParser(prog=args[0],
                                                description=descr)
        self.__init_arguments()
        self.__opts = vars(self.__parser.parse_args(self.__args))


    def GenerateConfig(self):
        cfg = []
        for opt_key, opt_val in self.__opts.items():
            if 'daemon' == opt_key:
                # Don't put 'daemon' into the generated config,
                # that is not a useful option for the OpenVPN 3 backend and we
                # handle this in the front-end instead.
                continue;
            key = opt_key.replace('_', '-')
            if isinstance(opt_val, bool):
                if opt_val is True:
                    cfg.append(key)
            elif isinstance(opt_val, list):
                for v in opt_val:
                    cfg.append('%s %s' %(key, v))
            elif opt_val is not None:
                if key in ('ca', 'cert', 'extra-certs', 'http-proxy-user-pass',
                           'key', 'tls-auth', 'tls-crypt'):
                    # Embedded files should not be prefixed by the key value
                    cfg.append(opt_val)
                else:
                    cfg.append('%s %s' % (key, opt_val))
        return '\n'.join(cfg)


    def GetConfigName(self):
        try:
            return getattr(self.__parser, 'config_name')
        except AttributeError:
            return None


    def GetDaemon(self):
        return self.__opts['daemon']


    def GetPersistTun(self):
        try:
            return self.__opts['persist_tun']
        except AttributeError:
            return False


    ##
    #  Checks if we have at least the pure minimum of options and arguments
    #  to establish a connection.
    #
    #  If not all required options are present, it will throw an execption
    #
    def SanityCheck(self):
        missing = []
        required = ('client', 'remote', 'ca')
        for req in required:
            if req in self.__opts:
                val = self.__opts[req]
                if val is None or val is False:
                    missing.append('--%s' % req)
                elif isinstance(val, list):
                    if 'remote' == req and len(val) < 1:
                        missing.append('--%s' % req)
                elif isinstance(val, str) and len(val) < 1:
                    missing.append('--%s' % req)

        if len(missing) > 0:
            raise Exception('The following options are missing to establish '
                            +' a connection: %s' % ', '.join(missing))


    def __init_arguments(self):
        self.__parser.add_argument('--auth', metavar='ALG',
                                   action='store',
                                   nargs=1,
                                   help='Authenticate packets with HMAC using'
                                   +' message digest algorithm alg'
                                   +' (default=SHA1)')

        # FIXME: Need to tackle loading creds from file, which is optional
        self.__parser.add_argument('--auth-user-pass',
                                   action='store_true',
                                   help='Authenticate with server using '
                                   + 'username/password')

        self.__parser.add_argument('--ca', metavar='FILE',
                                   action=ConfigParser.EmbedFile,
                                   help='Certificate authority file in '
                                   + '.pem format containing root certificate')

        self.__parser.add_argument('--cd', metavar='DIR',
                                   action=ConfigParser.ChangeDir,
                                   help='Change working directory to the given '
                                   + 'directory')

        self.__parser.add_argument('--cert', metavar='FILE',
                                   action=ConfigParser.EmbedFile,
                                   dest='cert', embed_tag='cert',
                                   help='Certificate authority file in .pem '
                                   + 'format by a Certificate Authority in '
                                   + '--ca file')

        self.__parser.add_argument('--cipher', metavar='ALG',
                                   action='store',
                                   help='Encrypt packets with cipher '
                                   +' algorithm alg'
                                   +' (default=BF-CBC)')

        self.__parser.add_argument('--client',
                                   action='store_true',
                                   help='Configures client configuration mode'
                                   + ' (mandatory)')

        self.__parser.add_argument('--comp-lzo', metavar='[MODE]',
                                   action=ConfigParser.OpenVPNvarArgs,
                                   help='Use LZO compression '
                                   + '(Deprecated, use --compress instead)')

        self.__parser.add_argument('--compress', metavar='[ALG]',
                                   action=ConfigParser.OpenVPNvarArgs,
                                   help='Compress using algorithm ALG')

        self.__parser.add_argument('--config', metavar='FILE',
                                   action=ConfigParser.ReadConfigFile,
                                   help='Read configuration options from file')

        self.__parser.add_argument('--daemon',
                                   action='store_true',
                                   help='Run the VPN tunnel in the background')

        self.__parser.add_argument('--dev', metavar='DEV-NAME',
                                   action='store',
                                   nargs=1,
                                   help='tun/tap device to use for VPN tunnel')

        self.__parser.add_argument('--dev-type', metavar='DEV-TYPE',
                                   action='store',
                                   nargs=1,
                                   help='Which device type are we using? tun '
                                   + 'or tap. Not needed if --dev starts with'
                                   + 'tun or tap')

        self.__parser.add_argument('--dhcp-option', metavar='OPTION [...]',
                                   action=ConfigParser.OpenVPNvarArgs,
                                   min_args=1,
                                   help='Set DHCP options which can be picked'
                                   + 'up by the OS configuring DNS, etc')

        self.__parser.add_argument('--extra-certs', metavar='FILE',
                                   action=ConfigParser.EmbedFile,
                                   dest='extra-certs', embed_tag='extra-certs',
                                   help='Specify a file containing one or '
                                   + 'more PEM certs (concatenated together) '
                                   + 'that complete the local certificate '
                                   + 'chain.')

        self.__parser.add_argument('--float',
                                   action='store_true',
                                   help='Allow remote to change its IP '
                                   + 'address/port')

        self.__parser.add_argument('--hand-window', metavar='SEC',
                                   action='store',
                                   nargs=1,
                                   help='Handshake window. The TLS-based key '
                                   + 'exchange must finalize within SEC '
                                   + 'seconds handshake initiation by any '
                                   + 'peer. (Default 60 seconds)')

        self.__parser.add_argument('--http-proxy',
                                   metavar='SRV PORT [auth] [auth-method]',
                                   action=ConfigParser.OpenVPNvarArgs,
                                   min_args=2,
                                   help='Connect to a remote host via an HTTP'
                                   + 'proxy at address SRV and port PORT. See'
                                   + ' manual for auth details')

        self.__parser.add_argument('--http-proxy-user-pass', metavar='FILE',
                                   action=ConfigParser.EmbedFile,
                                   help='Fetch HTTP proxy credentials from '
                                   + 'FILE')

        self.__parser.add_argument('--ifconfig',
                                   metavar='LOCAL NETMASK',
                                   action='store',
                                   nargs=2,
                                   help='Configure TUN/TAP device with LOCAL '
                                   + 'for local IPv4 address with netmask '
                                   + 'NETMASK')

        self.__parser.add_argument('--ifconfig-ipv6',
                                   metavar='LOCAL [REMOTE_ENDP]',
                                   action=ConfigParser.OpenVPNvarArgs,
                                   min_args=1,
                                   help='Configure TUN/TAP device with LOCAL '
                                   + 'for local IPv6 address and REMOTE_ENDP '
                                   + 'as the remote end-point')

        self.__parser.add_argument('--inactive', metavar='SECS [BYTES]',
                                   action=ConfigParser.OpenVPNvarArgs,
                                   min_args=1,
                                   help='Exit after n seconds of activity on '
                                   + 'TUN/TAP device. If BYTES is added, '
                                   + 'if bytes on the device is less than BYTES'
                                   + ' the tunnel will also exit')

        self.__parser.add_argument('--keepalive', metavar='P_SECS R_SECS',
                                   action='store',
                                   nargs=2,
                                   help='Ping remote every P_SECS second and '
                                   + 'restart tunnel if no response within '
                                   + 'R_SECS seconds')

        self.__parser.add_argument('--key', metavar='FILE',
                                   action=ConfigParser.EmbedFile,
                                   help='Local private key in .pem format')

        self.__parser.add_argument('--key-direction', metavar='DIR',
                                   action='store',
                                   choices=['0', '1'],
                                   nargs=1,
                                   help='Set key direction for static keys.'
                                   + ' Valid values: 0, 1')

        self.__parser.add_argument('--local', metavar='HOST',
                                   action='store',
                                   nargs=1,
                                   help='Local host name or IP address to '
                                   'to bind against on local side')

        self.__parser.add_argument('--lport', metavar='PORT',
                                   action='store',
                                   nargs=1,
                                   help='TCP/UDP port number for local bind '
                                   + '(default 1194)')

        self.__parser.add_argument('--mode', metavar='MODE',
                                   action='store',
                                   choices=['client'],
                                   nargs=1,
                                   help='Operational mode. Only "client" is'
                                   + 'accepted')

        self.__parser.add_argument('--mssfix', metavar='BYTES',
                                   action='store',
                                   nargs=1,
                                   help='Set upper bound on TCP MSS '
                                   + '(Default tun-mtu size)')

        client_server_ch = ['client', 'server']
        self.__parser.add_argument('--ns-cert-type', metavar='TYPE',
                                   action='store',
                                   choices=client_server_ch,
                                   nargs=1,
                                   help='(DEPRECATED) Require that peer '
                                   + 'certificate is signed with an explicit '
                                   + 'nsCertType designation.  '
                                   + 'Migrate to --remote-cert-tls ASAP. '
                                   + 'Valid values: '
                                   + ', '.join(client_server_ch))

        self.__parser.add_argument('--persist-tun',
                                   action='store_true',
                                   help='Keep tun/tap device open across '
                                   + 'connection restarts')

        self.__parser.add_argument('--ping', metavar='SECS',
                                   action='store',
                                   nargs=1,
                                   help='Ping remote once per SECS seconds')

        self.__parser.add_argument('--ping-restart', metavar='SECS',
                                   action='store',
                                   nargs=1,
                                   help='Restart if n seconds pass without '
                                   + 'reception of remote ping')

        self.__parser.add_argument('--pkcs12', metavar='FILE',
                                   action=ConfigParser.PKCS12Parser,
                                   help='PKCS#12 file containing local private '
                                   + 'key, local certificate and optionally '
                                   + 'the root CA certificate')

        self.__parser.add_argument('--port', metavar='PORT',
                                   action='store',
                                   nargs=1,
                                   help='TCP/UDP port number for both local '
                                   + 'and remote.')

        self.__parser.add_argument('--proto', metavar='PROTO',
                                   action='store',
                                   choices=['udp', 'tcp'],
                                   nargs=1,
                                   help='Use protocol PROTO for communicating '
                                   +'with peer. Valid values: udp, tcp')

        self.__parser.add_argument('--push-peer-info',
                                   action='store_true',
                                   help='Push client info to server')

        redirflags = ['autolocal', 'def1', 'bypass-dhcp'
                      'bypass-dns', 'block-local',
                      'ipv4', '!ipv4', 'ipv6', '!ipv6']
        self.__parser.add_argument('--redirect-gateway', metavar='[FLAGS]',
                                   choices=redirflags,
                                   action=ConfigParser.OpenVPNvarArgs,
                                   help='Automatically execute routing '
                                   + 'commands to redirect all outgoing IP '
                                   + 'traffic through the VPN.  Valid flags: '
                                   + ', '.join(redirflags))

        self.__parser.add_argument('--redirect-private', metavar='[FLAGS]',
                                   choices=redirflags,
                                   action=ConfigParser.OpenVPNvarArgs,
                                   help='Like --redirect-gateway, but omit '
                                   + 'actually changing default gateway.'
                                   + 'Valid flags: ' + ', '.join(redirflags))

        self.__parser.add_argument('--remote', metavar='HOST [PORT [PROTO]]',
                                   action=ConfigParser.OpenVPNvarArgs,
                                   min_args=1,
                                   help='Remote host or IP. PORT number and '
                                   'PROTO are optional. May be provided '
                                   'multiple times.')

        self.__parser.add_argument('--remote-cert-eku', metavar='OID',
                                   action=ConfigParser.OpenVPNvarArgs,
                                   min_args=1,
                                   help='Require the peer certificate to be '
                                   + 'signed with explicit extended key usage. '
                                   + 'OID can be an object identifier or '
                                   + 'OpenSSL string representation.')

        self.__parser.add_argument('--remote-cert-ku', metavar='ID',
                                   action=ConfigParser.OpenVPNvarArgs,
                                   min_args=1,
                                   help='Require that the peer certificate was '
                                   + 'signed with explicit key usage (ID). '
                                   + 'More than one ID can be provided. Must '
                                   + 'be hexadecimal notation of integers')

        self.__parser.add_argument('--remote-cert-tls', metavar='TYPE',
                                   action='store',
                                   choices=client_server_ch,
                                   nargs=1,
                                   help='Require that peer certificate is '
                                   + 'signed with explicit key usage and '
                                   + 'extended key usage based RFC3280 rules. '
                                   + 'Valid values: '
                                   + ', '.join(client_server_ch))

        self.__parser.add_argument('--remote-random',
                                   action='store_true',
                                   help='If multiple --remote options '
                                   + 'specified, choose one randomly')

        self.__parser.add_argument('--reneg-sec', metavar='SECS',
                                   action='store',
                                   nargs=1,
                                   help='Renegotiate data channel key after '
                                   + 'SECS seconds. (Default 3600)')

        self.__parser.add_argument('--route',
                                   metavar='NETWORK [NETMASK [GATEWAY '
                                   + '[METRIC]]]',
                                   action=ConfigParser.OpenVPNvarArgs,
                                   min_args=1,
                                   help='Add route to routing table after '
                                   + 'connection is established.  Multiple '
                                   + 'routes can be specified. Default '
                                   + 'NETMASK: 255.255.255.255.  Default '
                                   + 'GATEWAY is taken from --route-gateway '
                                   + 'or --ifconfig')

        self.__parser.add_argument('--route-gateway', metavar='[GW|dhcp]',
                                   action='store',
                                   nargs=1,
                                   help='Specify a default gateway for use '
                                   + 'with --route. See man page for dhcp mode')

        self.__parser.add_argument('--route-ipv6',
                                   metavar='NETWORK/PREFIX [GATEWAY [METRIC]]',
                                   action=ConfigParser.OpenVPNvarArgs,
                                   min_args=1,
                                   help='Add IPv6 route to routing table after '
                                   + 'connection is established.  Multiple '
                                   + 'routes can be specified. Default GATEWAY '
                                   + 'is taken from \'remote\' in '
                                   + '--ifconfig-ipv6')

        self.__parser.add_argument('--route-metric', metavar='METRIC',
                                   action='store',
                                   nargs=1,
                                   help='Specify a default metric for use with '
                                   + '--route')

        self.__parser.add_argument('--route-nopull',
                                   action='store_true',
                                   help='Do not configure routes pushed by '
                                   + 'remote server')

        self.__parser.add_argument('--server-poll-timeout', metavar='SECS',
                                   action='store',
                                   nargs=1,
                                   help='How long to wait for a response from '
                                   + 'a remote server during connection setup '
                                   + ' (Default 120 seconds)')

        self.__parser.add_argument('--setenv', metavar='NAME [VALUE]',
                                   action=ConfigParser.OpenVPNvarArgs,
                                   min_args=1,
                                   help='Set a custom environmental variable '
                                   + 'to pass to script.')

        self.__parser.add_argument('--static-challenge', metavar='MSG ECHO',
                                   action=ConfigParser.OpenVPNvarArgs,
                                   min_args=2,
                                   help='Enable static challenge/response '
                                   + 'protocol using challenge text MSG, with '
                                   + 'ECHO indicating echo flag (0|1)')

        self.__parser.add_argument('--tcp-queue-limit', metavar='NUM',
                                   action='store',
                                   nargs=1,
                                   help='Maximum number of queued TCP output '
                                   + 'packets')

        self.__parser.add_argument('--tls-auth', metavar='FILE [DIR]',
                                   action=ConfigParser.EmbedTLSauth,
                                   help='Add additional HMAC auth on TLS '
                                   + 'control channel. FILE must be a shared '
                                   + 'secret. DIR is optional and defines '
                                   + 'which sub-keys in FILE to use for '
                                   + 'HMAC signing and verification')

        cert_profiles = ['legacy','preferred','suiteb']
        self.__parser.add_argument('--tls-cert-profile', metavar='PROFILE',
                                   action='store',
                                   choices=cert_profiles,
                                   help='Sets certificate profile which '
                                   + 'defines acceptable crypto algorithms. '
                                   + 'Valid profiles: '
                                   + ', '.join(cert_profiles))

        self.__parser.add_argument('--tls-client',
                                   action='store_true',
                                   help='Enable TLS and assume client role '
                                   + 'during TLS handshake. Implicitly added '
                                   + 'when using --client')

        self.__parser.add_argument('--tls-crypt', metavar='FILE',
                                   action=ConfigParser.EmbedFile,
                                   help='Encrypts the TLS control channel '
                                   + 'with a shared secret key (FILE).  This'
                                   + 'CANNOT be combined with --tls-auth')

        self.__parser.add_argument('--tls-timeout', metavar='SECS',
                                   action='store',
                                   help='Packet retransmit timeout on TLS '
                                   + 'control channel if no ACK from remote '
                                   + 'within n seconds (Default 2 seconds')

        topologies = ['subnet', 'net30']
        self.__parser.add_argument('--topology', metavar='TYPE',
                                   action='store',
                                   choices=topologies,
                                   nargs=1,
                                   help='Set tunnel topology type. '
                                   + 'Default is net30. Recommended: subnet.'
                                   + 'Valid topologies: '
                                   + ', '.join(topologies))

        self.__parser.add_argument('--tran-window', metavar='SECS',
                                   action='store',
                                   nargs=1,
                                   help='Transition window -- old data channel '
                                   + 'key can live this many seconds after new'
                                   + 'after new key renegotiation begins '
                                   + '(Default 3600 secs)')

        self.__parser.add_argument('--tun-mtu', metavar='SIZE',
                                   action='store',
                                   nargs=1,
                                   help='Set TUN/TAP device MTU to SIZE and '
                                   + 'derive TCP/UDP from it (default is 1500)')

        self.__parser.add_argument('--verb',
                                   metavar= 'LEVEL',
                                   action='store',
                                   nargs=1,
                                   help='Set log verbosity level.  Log levels '
                                   +'are NOT compatible with OpenVPN 2 --verb ')


        descr = 'The following options are ignored and not processed.  These ' \
        + 'options are not implemented in the OpenVPN 3 Core library ' \
        + 'and will not break existing configurations.'
        ignored = self.__parser.add_argument_group('Ignored options', descr)

        ignored.add_argument('--chroot',
                             metavar='DIR',
                             action=ConfigParser.IgnoreArg,
                             nargs=1,
                             help='Chroot to this directory after '
                             + 'initialization. Not applicable with OpenVPN 3, '
                             + 'which uses a different execution model.')

        ignored.add_argument('--explicit-exit-notify',
                             metavar='[ATTEMPTS]',
                             action=ConfigParser.IgnoreArg,
                             nargs='+',
                             help='On exit/restart, send exit signal to remote '
                             + 'end. Automatically configured with OpenVPN 3')

        ignored.add_argument('--group',
                             metavar='GROUP',
                             action=ConfigParser.IgnoreArg,
                             nargs=1,
                             help='Run OpenVPN with GROUP group credentials. '
                             + 'Not needed with OpenVPN 3 which uses a '
                             + 'different privilege separation approach')

        ignored.add_argument('--nice',
                             metavar='LEVEL',
                             action=ConfigParser.IgnoreArg,
                             nargs=1,
                             help='Change process priority. Not supported in '
                             + 'OpenVPN 3')

        ignored.add_argument('--nobind',
                             action=ConfigParser.IgnoreArg,
                             nargs=0,
                             help='Do not bind to local address and port. '
                             + 'This is default behaviour in OpenVPN 3')

        ignored.add_argument('--persist-key',
                             action=ConfigParser.IgnoreArg,
                             nargs=0,
                             help='Do not re-read key files across connection '
                             + 'restarts. Not needed. OpenVPN 3 keeps keys '
                             + 'as embedded file elements in the configuration')

        ignored.add_argument('--rcvbuf',
                             metavar='SIZE',
                             action=ConfigParser.IgnoreArg,
                             nargs=1,
                             help='Set the TCP/UDP receive buffer size. Not '
                             + 'supported in OpenVPN 3')

        ignored.add_argument('--resolv-retry',
                             metavar='SECS',
                             action=ConfigParser.IgnoreArg,
                             nargs=1,
                             help='If hostname resolve fails for --remote, '
                             + 'retry resolve for n seconds before failing. '
                             + 'Not supported by OpenVPN 3')

        ignored.add_argument('--sndbuf',
                             metavar='SIZE',
                             action=ConfigParser.IgnoreArg,
                             nargs=1,
                             help='Set the TCP/UDP send buffer size. Not '
                             + 'supported in OpenVPN 3')

        ignored.add_argument('--socket-flags',
                             metavar='FLAGS',
                             action=ConfigParser.IgnoreArg,
                             nargs='+',
                             help='Applies flags to the transport socket. Not '
                             + 'supported in OpenVPN 3')

        ignored.add_argument('--user',
                             metavar='USER',
                             action=ConfigParser.IgnoreArg,
                             nargs=1,
                             help='Run OpenVPN with USER user credentials. '
                             + 'Not needed with OpenVPN 3 which uses a '
                             + 'different privilege separation approach')

        ignored.add_argument('--verify-x509-name',
                             metavar='SUBJECT [FLAGS]',
                             action=ConfigParser.IgnoreArg,
                             nargs='+',
                             help='Accept connections only with a host with '
                             + 'X509 subject.  Not yet implemented in '
                             + 'OpenVPN 3')
        # ENDFNC: __init_arguments()


    ##
    #  Special argparser extension which is capable of parsing
    #  a configuration file.  And it handles recursive inclusion, so
    #  configuration files may contain the 'config' to include other
    #  settings to the main configuration
    #
    class ReadConfigFile(argparse.Action):
        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            super(ConfigParser.ReadConfigFile, self).__init__(option_strings, dest, **kwargs)

        def __call__(self, parser, namespace, values, option_string=None):
            #
            # Parse the configuration file
            #
            fp = open(values, 'r')

            # Remove new line markers on each line and only consider lines which
            # has not been commented out
            cfg = []
            embedded = {}
            tmp = None
            embedded_key = None
            for opt in [l.strip() for l in fp.readlines() if 0 < len(l.split('#')[0])]:
                if len(opt) == 0:
                    # Skip empty lines
                    continue

                # Check if we have a start-tag for embedded blob
                # An embedded blob is always the option name enclosed in
                # '<' and '>'.  The end of the embedded blob is closed with
                # '</option-name>'.
                if embedded_key is None and opt[0] == '<':
                    # Embedded blob found.  When embedded_key is _NOT_ None, we
                    # are inside an embedded blob tag.
                    tmp = [opt,]
                    embedded_key = opt[1:len(opt)-1]
                elif embedded_key is not None and '</' + embedded_key + '>' != opt:
                    # When inside an embedded blob, save the contents
                    tmp.append(opt)
                elif embedded_key is not None and '</' + embedded_key + '>' == opt:
                    # On closure of the embedded blob, save it separately.  This
                    # should not be parsed by the argument parser further.
                    tmp.append(opt)
                    embedded[embedded_key] = '\n'.join(tmp)
                    embedded_key = None
                else:
                    # When outside an embedded blob, copy the option and its
                    # arguments to be parsed further
                    cfg.append('--' + opt)

            # Parse the collected arguments further and merge them with the
            # already parsed argument
            args = vars(parser.parse_args(shlex.split('\n'.join(cfg),
                                                      posix=False)))
            for (k,v) in args.items():
                setattr(namespace, k, v)

            # Merge in embedded blobs, without further parsing
            for (k,v) in embedded.items():
                setattr(namespace, k, v)

            # Remove the option triggering this call from the namespace.
            # This option (self.dest) is not needed as the provided config file
            # has already been parsed and embedded.
            #
            # There is one exception though, the very first --config will be
            # preserverd, and stored as config_name.
            if 'config' == self.dest:
                try:
                    cfgname = getattr(parser, 'config_name')
                except AttributeError:
                    setattr(parser, 'config_name', values)
            delattr(namespace, self.dest)
        # ENDFNC: ReadConfigFile::__call__()
    # ENDCLASS: ReadConfigFile

    ##
    #  Some OpenVPN options may take one or more arguments.  This tackles
    #  these odd cases
    class OpenVPNvarArgs(argparse.Action):
            def __init__(self, option_strings, dest, nargs=None, **kwargs):
                try:
                    self.__min_args = kwargs.pop('min_args')
                except KeyError:
                    self.__min_Args = 0
                super(ConfigParser.OpenVPNvarArgs, self).__init__(option_strings, dest, '*', **kwargs)

            def __call__(self, parser, namespace, values, option_string=None):
                # Always presume that these types of options can be
                # enslisted multiple times.  So we will always extend
                # a list where self.dest matches an existing key

                dst = getattr(namespace, self.dest)
                if dst is None:
                    dst = []

                min_args = 0
                try:
                    min_args = self.__min_args
                except AttributeError:
                    pass

                if isinstance(values, list):
                    if len(values) < min_args:
                        err = 'The --%s requires at least %i arguments' % (self.dest, min_args)
                        raise argparse.ArgumentError(self, err)

                    dst.append(' '.join(values))
                else:
                    dst.append(values)

                setattr(namespace, self.dest, dst)


    class ChangeDir(argparse.Action):
        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            super(ConfigParser.ChangeDir, self).__init__(option_strings, dest, '+', **kwargs)

        def __call__(self, parser, namespace, values, option_string=None):
            """Changes the current working directory to the provided one
            """

            os.chdir(values[0])
            setattr(namespace, self.dest, values[0])

    ##
    #  Options related to keying material needs to be embedded in an
    #  OpenVPN 3 configuration profile.  This argparser extension
    #  will generate an embedded file option on-the-fly
    #
    class EmbedFile(argparse.Action):
        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            # Add a new argument to the add_argument() method
            # The embed_tag variable is the tag name used when
            # generating the tag.  If not set, use the same as the
            # destination name
            if 'embed_tag' in kwargs:
                self.__tag = kwargs.pop('embed_tag')
            else:
                self.__tag = dest
            super(ConfigParser.EmbedFile, self).__init__(option_strings, dest, nargs, **kwargs)

        def __call__(self, parser, namespace, values, option_string=None):
            """Loads the given file and generates an embedded option of it"""

            try:
                fp = open(values, 'r')
                ret = '<%s>\n' % self.__tag
                ret += '\n'.join([l.strip() for l in fp.readlines()])
                ret += '\n</%s>' % self.__tag
                fp.close()
                setattr(namespace, self.dest, ret)
            except IOError as e:
                err = str(e.strerror) + " '" + values + "'"
                raise argparse.ArgumentError(self, err)

    # ENDCLASS: EmbedFile


    class EmbedTLSauth(EmbedFile):
        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            # Add a new argument to the add_argument() method
            # The embed_tag variable is the tag name used when
            # generating the tag.  If not set, use the same as the
            # destination name
            if 'embed_tag' in kwargs:
                self.__tag = kwargs.pop('embed_tag')
            else:
                self.__tag = 'tls-auth'
            super(ConfigParser.EmbedFile, self).__init__(option_strings, dest, '+', **kwargs)

        def __call__(self, parser, namespace, values, option_string=None):
            """Loads the tls-auth file, generates an embedded option of it
            and considers if there is a key-direction argument as well
            """

            # If values is a list, we have filename and key-direction
            filename = values
            if isinstance(values, list):
                setattr(namespace, 'key-direction', values[1])
                filename = values[0]

            fp = open(filename, 'r')
            ret = '<%s>\n' % self.__tag
            ret += '\n'.join([l.strip() for l in fp.readlines()])
            ret += '\n</%s>' % self.__tag
            fp.close()
            setattr(namespace, self.dest, ret)


    ##
    #  Special file parser for PKCS12 files.  Will extract keys and
    #  certificates and embed them to the configuration as embedded files
    #
    class PKCS12Parser(argparse.Action):
        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            super(ConfigParser.PKCS12Parser, self).__init__(option_strings, dest, **kwargs)

        def __call__(self, parser, namespace, values, option_string=None):
            # Bail out with an error if we don't have pyOpenSSL installed
            if not HAVE_OPENSSL:
                raise Exception('pyOpenSSL library is not installed.  '
                                + 'Cannot parse PKCS#12 files.')

            # Read the PKCS12 file into a memory buffer (p12bin)
            # and decode it (p12)
            with open(values, 'rb') as f:
                p12bin = f.read()
            p12 = None

            # First try without password
            try:
                p12 = crypto.load_pkcs12(p12bin)
            except crypto.Error as e:
                if 'PKCS12_parse' == e.message[0][1] and \
                   'mac verify failure' == e.message[0][2]:
                    # Password is needed.  Query the user for it
                    p12 = crypto.load_pkcs12(p12bin,
                                             getpass('PKCS12 passphrase: '))

            # Extract CA, certificate and private key
            d = '<key>\n%s</key>' % (crypto.dump_privatekey(crypto.FILETYPE_PEM,
                                                          p12.get_privatekey()))
            setattr(namespace, 'key', d)

            d = '<cert>\n%s</cert>' % (crypto.dump_certificate(crypto.FILETYPE_PEM,
                                                          p12.get_certificate()))
            setattr(namespace, 'cert', d)

            cacerts = []
            for c in p12.get_ca_certificates():
                cacerts.append(crypto.dump_certificate(crypto.FILETYPE_PEM,
                                                       c))
            if 0 < len(cacerts):
                d = '<ca>\n%s</ca>' % (''.join(cacerts),)
                setattr(namespace, 'ca', d)

            # We don't want to save this option, it is not useful as
            # we've already split up the PKCS#12 file into appropriate
            # sub-elements
            delattr(namespace, 'pkcs12')
        # ENDFNC: PKCS12Parser::__call__()
    # ENDCLASS: PKCS12Parser


    ##
    #  Options using this argparse.Action variant will just be ignored
    #  and never passed on further for the following parsing
    class IgnoreArg(argparse.Action):
        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            super(ConfigParser.IgnoreArg, self).__init__(option_strings, dest, nargs, **kwargs)

        def __call__(self, parser, namespace, values, options_string):
            # Ensure this option/argument is not preserved
            delattr(namespace, self.dest)
# ENDCLASS: ConfigParser
