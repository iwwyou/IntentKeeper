pragma solidity ^0.6.12;

abstract contract Context {
    function _msgSender() internal view virtual returns (address payable) {
        return msg.sender;
    }

    function _msgData() internal view virtual returns (bytes memory) {
        return msg.data;
    }
}

contract Ownable is Context {
    address private _owner;
    address private _previousOwner;
    uint256 private _lockTime;

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    constructor () internal {
        address msgSender = _msgSender();
        _owner = msgSender;
        emit OwnershipTransferred(address(0), msgSender);
    }

    function owner() public view returns (address) {
        return _owner;
    }

    modifier onlyOwner() {
        require(_owner == _msgSender(), "Ownable: caller is not the owner");
        _;
    }

    function renounceOwnership() public virtual onlyOwner {
        emit OwnershipTransferred(_owner, address(0));
        _owner = address(0);
    }

    function transferOwnership(address newOwner) public virtual onlyOwner {
        require(newOwner != address(0), "Ownable: new owner is the zero address");
        emit OwnershipTransferred(_owner, newOwner);
        _owner = newOwner;
    }

    function getUnlockTime() public view returns (uint256) {
        return _lockTime;
    }
}

contract SwordCrowdsale is Ownable {
    struct Contributor {
        uint256 contributionAmount;
        uint256 tokensIssued;
    }

    mapping(address => Contributor) public contributorList;

    uint256 public weiRaised;
    address payable public wallet;

    constructor(address payable _wallet) public {
        wallet = _wallet;
    }

    function contribute() external payable {
        contributorList[msg.sender].contributionAmount += msg.value;
        weiRaised += msg.value;
    }

    function forwardAllRaisedFunds() internal {
        wallet.transfer(weiRaised);
    }

    function refundMoney(address payable _address) public onlyOwner {
        uint256 amount = contributorList[_address].contributionAmount;
        if (amount > 0 && _address.send(amount)) {
            contributorList[_address].contributionAmount = 0;
            contributorList[_address].tokensIssued = 0;
        }
        // @Post weiRaised(Entry > Exit)
    }
}
