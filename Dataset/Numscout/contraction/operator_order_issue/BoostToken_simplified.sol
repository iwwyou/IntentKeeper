pragma solidity ^0.6.12;

library SafeMath {
    function div(uint256 a, uint256 b) internal pure returns (uint256) {
        return a / b;
    }
    function mul(uint256 a, uint256 b) internal pure returns (uint256) {
        return a * b;
    }
}

library Address {
}

contract BoostToken {
    using SafeMath for uint256;
    using Address for address;

    address payable public _devWalletAddress;
    address payable public _marketingWalletAddress;
    address payable public _dipWalletAddress;
    address payable public _marketingWalletAddress2;

    function sendETHToTeam(uint256 amount) private {
        _devWalletAddress.transfer(amount.div(4));
        _marketingWalletAddress.transfer(amount.div(12).mul(5));
        _dipWalletAddress.transfer(amount.div(9).mul(2));
        _marketingWalletAddress2.transfer(amount.div(9));
    }
}
