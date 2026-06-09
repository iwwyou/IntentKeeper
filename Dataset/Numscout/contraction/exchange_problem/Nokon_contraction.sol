pragma solidity 0.7.4;

interface IERC20 {

    function totalSupply() external view returns (uint256);

    function balanceOf(address account) external view returns (uint256);

    function allowance(address _owner, address spender) external view returns (uint256);

    function transfer(address recipient, uint256 amount) external returns (bool);

    function approve(address spender, uint256 amount) external returns (bool);

    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
}

contract Nokon is IERC20 {
    using SafeMath for uint256;

    event Bought(uint256 amountz);

    event Sold(uint256 amount);

    event Approval(address indexed tokenOwner, address indexed spender, uint tokens);

    event Transfer(address indexed _from, address indexed _to, uint tokens);

    mapping(address => uint256) balances;
    bool presell = true;
    uint256 ethRateFix = 10000000000; 

    function balanceOf(address tokenOwner) public override view returns (uint256) {
        return balances[tokenOwner];
    }   

    function calculateRate() private returns (uint256){
        uint256 balance = balanceOf(address(this));
        if (balance > 100000000000000000) {
            return 666666;
        }
        if (balance > 50000000000000000) {
            return 333333;
        }
        return 250000;
    }

    function buy() public payable {
        require(presell, "presell is closed");
        uint256 minBuy = 50000000000000000;
        uint256 amountToBuy = msg.value / ethRateFix * calculateRate();
        uint256 dexBalance = balanceOf(address(this));
        require(msg.value >= minBuy, "minimum buy is 0.05 eth");

        require(amountToBuy < dexBalance, "not enough token in reserve");

        balances[address(this)] = balances[address(this)] - amountToBuy;
        balances[msg.sender] = balances[msg.sender] + amountToBuy;
        emit Transfer(address(this), msg.sender, amountToBuy);
        emit Bought(amountToBuy);
    }
}