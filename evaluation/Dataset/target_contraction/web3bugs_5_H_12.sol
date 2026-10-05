pragma solidity 0.8.3;

contract Pools {

    bool private inited;
    uint public pooledVADER;
    uint public pooledUSDV;

    address public VADER;
    address public USDV;
    address public ROUTER;
    address public FACTORY;

    mapping(address => bool) _isMember;
    mapping(address => bool) _isAsset;
    mapping(address => bool) _isAnchor;

    mapping(address => uint) public mapToken_Units;
    mapping(address => mapping(address => uint)) public mapTokenMember_Units;
    mapping(address => uint) public mapToken_baseAmount;
    mapping(address => uint) public mapToken_tokenAmount;

    function getAddedAmount(address _token, address _pool) internal returns(uint addedAmount) {
        uint _balance = iERC20(_token).balanceOf(address(this));
        if(_token == VADER && _pool != VADER){
            addedAmount = _balance - pooledVADER;
            pooledVADER = pooledVADER + addedAmount;
        } else if(_token == USDV) {
            addedAmount = _balance - pooledUSDV;
            pooledUSDV = pooledUSDV + addedAmount;
        } else {
            addedAmount = _balance - mapToken_tokenAmount[_pool];
        }
    }    
}
