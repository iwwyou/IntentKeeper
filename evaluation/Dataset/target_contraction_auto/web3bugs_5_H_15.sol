pragma solidity 0.8.3;

contract Router {

    bool private inited;
    uint one = 10**18;
    uint public rewardReductionFactor;
    uint public timeForFullProtection;

    uint public curatedPoolLimit;
    uint public curatedPoolCount;
    mapping(address => bool) private _isCurated;

    address public VADER;
    address public USDV;
    address public POOLS;

    uint public anchorLimit;
    uint public insidePriceLimit;
    uint public outsidePriceLimit;
    address[] public arrayAnchors;
    uint[] public arrayPrices;

    uint public repayDelay = 3600;

    mapping(address => mapping(address => uint)) public mapMemberToken_depositBase;
    mapping(address => mapping(address => uint)) public mapMemberToken_depositToken;
    mapping(address => mapping(address => uint)) public mapMemberToken_lastDeposited;

    mapping(address => CollateralDetails) private mapMember_Collateral;
    mapping(address => mapping(address => uint)) private mapCollateralDebt_Collateral;
    mapping(address => mapping(address => uint)) private mapCollateralDebt_Debt;
    mapping(address => mapping(address => uint)) private mapCollateralDebt_interestPaid;
    mapping(address => mapping(address => uint)) private mapCollateralAsset_NextEra;

    struct CollateralDetails {
        uint ID;
        mapping(address => DebtDetails) mapCollateral_Debt;
    }
    struct DebtDetails{
        uint ID;
        mapping(address =>uint) debt;
        mapping(address =>uint) collateral;
    }

    event PoolReward(address indexed base, address indexed token, uint amount);

    function swap(uint inputAmount, address inputToken, address outputToken) external returns (uint outputAmount) {
        return swapWithSynthsWithLimit(inputAmount, inputToken, false, outputToken, false, 10000);
    }

    function swapWithSynthsWithLimit(uint inputAmount, address inputToken, bool inSynth, address outputToken, bool outSynth, uint slipLimit) public returns (uint outputAmount) {
        address _member = msg.sender;
        if(!inSynth){
            moveTokenToPools(inputToken, inputAmount);
        } else {
            moveTokenToPools(iPOOLS(POOLS).getSynth(inputToken), inputAmount);
        }
        address _base;
        if(iPOOLS(POOLS).isAnchor(inputToken) || iPOOLS(POOLS).isAnchor(outputToken)) {
            _base = VADER;
        } else {
            _base = USDV;
        }
        if (isBase(outputToken)) {
            require(iUTILS(UTILS()).calcSwapSlip(inputAmount, iPOOLS(POOLS).getTokenAmount(inputToken)) <= slipLimit);
            if(!inSynth){
                outputAmount = iPOOLS(POOLS).swap(_base, inputToken, _member, true);
            } else {
                outputAmount = iPOOLS(POOLS).burnSynth(_base, inputToken, _member);
            }
        } else if (isBase(inputToken)) {
            require(iUTILS(UTILS()).calcSwapSlip(inputAmount, iPOOLS(POOLS).getBaseAmount(outputToken)) <= slipLimit);
            if(!outSynth){
                outputAmount = iPOOLS(POOLS).swap(_base, outputToken, _member, false);
            } else {
                outputAmount = iPOOLS(POOLS).mintSynth(_base, outputToken, _member);
            }
        } else if (!isBase(inputToken) && !isBase(outputToken)) {
            require(iUTILS(UTILS()).calcSwapSlip(inputAmount, iPOOLS(POOLS).getTokenAmount(inputToken)) <= slipLimit);
            if(!inSynth){
                iPOOLS(POOLS).swap(_base, inputToken, POOLS, true);
            } else {
                iPOOLS(POOLS).burnSynth(_base, inputToken, POOLS);
            }
            require(iUTILS(UTILS()).calcSwapSlip(inputAmount, iPOOLS(POOLS).getBaseAmount(outputToken)) <= slipLimit);
            if(!outSynth){
                outputAmount = iPOOLS(POOLS).swap(_base, outputToken, _member, false);
            } else {
                outputAmount = iPOOLS(POOLS).mintSynth(_base, outputToken, _member);
            }
        }
        _handlePoolReward(_base, inputToken);
        _handlePoolReward(_base, outputToken);
        _handleAnchorPriceUpdate(inputToken);
        _handleAnchorPriceUpdate(outputToken);
    }

    function _handlePoolReward(address _base, address _token) internal{
        if(!isBase(_token)){
            uint _reward = iUTILS(UTILS()).getRewardShare(_token, rewardReductionFactor);
            iERC20(_base).transfer(POOLS, _reward);
            iPOOLS(POOLS).sync(_base, _token);
            emit PoolReward(_base, _token, _reward);
        }
    }

    function updateAnchorPrice(address token) public {
        for(uint i = 0; i<arrayAnchors.length; i++){
            if(arrayAnchors[i] == token){
                arrayPrices[i] = iUTILS(UTILS()).calcValueInBase(arrayAnchors[i], one);
            }
        }
    }

    function _handleAnchorPriceUpdate(address _token) internal{
        if(iPOOLS(POOLS).isAnchor(_token)){
            updateAnchorPrice(_token);
        }
    }

    function isBase(address token) public view returns(bool base) {
        if(token == VADER || token == USDV){
            return true;
        }
    }

    function moveTokenToPools(address _token, uint _amount) internal returns(uint safeAmount) {
        if(_token == VADER || _token == USDV || iPOOLS(POOLS).isSynth(_token)){
            safeAmount = _amount;
            if(tx.origin==msg.sender){
                iERC20(_token).transferTo(POOLS, _amount);
            }else{
                iERC20(_token).transferFrom(msg.sender, POOLS, _amount);
            }
        } else {
            uint _startBal = iERC20(_token).balanceOf(POOLS);
            iERC20(_token).transferFrom(msg.sender, POOLS, _amount);
            safeAmount = iERC20(_token).balanceOf(POOLS) - _startBal;
        }
    }

    function UTILS() public view returns(address){
        return iVADER(VADER).UTILS();
    }

}
