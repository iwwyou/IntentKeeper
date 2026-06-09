pragma solidity 0.7.6;

interface IVerification {
    event VerifierAdded(address indexed verifier);

    event VerifierRemoved(address indexed verifier);

    event UserRegistered(address indexed masterAddress, address indexed verifier, uint256 activatesAt);

    event UserUnregistered(address indexed masterAddress, address indexed verifier, address indexed unregisteredBy);

    event AddressLinked(address indexed linkedAddress, address indexed masterAddress, uint256 activatesAt);

    event AddressUnlinked(address indexed linkedAddress, address indexed masterAddress);

    event AddressLinkingRequested(address indexed linkedAddress, address indexed masterAddress);

    event AddressLinkingRequestCancelled(address indexed linkedAddress, address indexed masterAddress);

    event ActivationDelayUpdated(uint256 activationDelay);

    function isUser(address _user, address _verifier) external view returns (bool isMsgSenderUser);

    function verifiers(address _verifier) external view returns (bool isValid);

    function registerMasterAddress(address _masterAddress, bool _isMasterLinked) external;

    function unregisterMasterAddress(address _masterAddress, address _verifier) external;
}
