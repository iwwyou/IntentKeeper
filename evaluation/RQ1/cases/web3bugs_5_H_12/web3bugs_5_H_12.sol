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
        // @LocalVar _token = symbolicAddress 1
        // @LocalVar _pool = symbolicAddress 2
        // @StateVar VADER = symbolicAddress 3
        // @StateVar USDV = symbolicAddress 4
        // @IReturn iERC20(_token).balanceOf() = [200, 200]
        // @StateVar mapToken_tokenAmount[1] = [100, 100]
        // @StateVar mapToken_tokenAmount[2] = [50, 50]
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
        // @Post returnExpression == _balance - mapToken_tokenAmount[_token]
    }
}
