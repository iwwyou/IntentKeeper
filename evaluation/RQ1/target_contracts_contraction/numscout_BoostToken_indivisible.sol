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

contract BoostToken is Context, Ownable {
    using SafeMath for uint256;
    using Address for address;

    event botAddedToBlacklist(address account);

    event botRemovedFromBlacklist(address account);

    mapping (address => uint256) private _rOwned;
    mapping (address => uint256) private _tOwned;
    mapping (address => mapping (address => uint256)) private _allowances;
    mapping (address => bool) private _isExcludedFromFee;
    mapping (address => bool) private _isExcluded;
    address[] private _excluded;
    mapping (address => bool) private _isBlackListedBot;
    address[] private _blackListedBots;
    uint256 private constant MAX = ~uint256(0);
    uint256 private constant _tTotal = 1000000000 * 10**18;
    uint256 private _rTotal = (MAX - (MAX % _tTotal));
    address payable public _devWalletAddress;
    address payable public _marketingWalletAddress;
    address payable public _dipWalletAddress;
    address payable public _marketingWalletAddress2;
    IUniswapV2Router02 public uniswapV2Router;
    address public uniswapV2Pair;
    bool inSwap = false;
    bool public swapEnabled = true;
    uint256 private _maxTxAmount = 5000000 * 10**18;
    uint256 private constant _numOfTokensToExchangeForTeam = 5000 * 10**18;
    uint256 private _maxWalletSize = 9500000 * 10**18;

    modifier lockTheSwap {
        inSwap = true;
        _;
        inSwap = false;
    }

    function _getCurrentSupply() private view returns(uint256, uint256) {
        uint256 rSupply = _rTotal;
        uint256 tSupply = _tTotal;
        for (uint256 i = 0; i < _excluded.length; i++) {
            if (_rOwned[_excluded[i]] > rSupply || _tOwned[_excluded[i]] > tSupply) {
                return (_rTotal, _tTotal);
            }
            rSupply = rSupply.sub(_rOwned[_excluded[i]]);
            tSupply = tSupply.sub(_tOwned[_excluded[i]]);
        }
        if (rSupply < _rTotal.div(_tTotal)) {
            return (_rTotal, _tTotal);
        }
        return (rSupply, tSupply);
    }

    function _getRate() private view returns(uint256) {
        (uint256 rSupply, uint256 tSupply) = _getCurrentSupply();
        return rSupply.div(tSupply);
    }

    function tokenFromReflection(uint256 rAmount) public view returns(uint256) {
        require(rAmount <= _rTotal, "Amount must be less than total reflections");
        uint256 currentRate =  _getRate();
        return rAmount.div(currentRate);
    }

    function balanceOf(address account) public view override returns (uint256) {
        if (_isExcluded[account]) {
            return _tOwned[account];
        }
        return tokenFromReflection(_rOwned[account]);
    }

    function swapTokensForEth(uint256 tokenAmount) private lockTheSwap{           
        address[] memory path = new address[](2);
        path[0] = address(this);
        path[1] = uniswapV2Router.WETH();

        _approve(address(this), address(uniswapV2Router), tokenAmount);
       
        uniswapV2Router.swapExactTokensForETHSupportingFeeOnTransferTokens(
            tokenAmount,
            0,
            path,
            address(this),
            block.timestamp
        );
    }

    function sendETHToTeam(uint256 amount) private {
        _devWalletAddress.transfer(amount.div(4));
        _marketingWalletAddress.transfer(amount.div(12).mul(5));
        _dipWalletAddress.transfer(amount.div(9).mul(2));
        _marketingWalletAddress2.transfer(amount.div(9));
    }

    function _transfer(address sender, address recipient, uint256 amount) private {
        require(sender != address(0), "ERC20: transfer from the zero address");
        require(recipient != address(0), "ERC20: transfer to the zero address");
        require(amount > 0, "Transfer amount must be greater than zero");
        require(!_isBlackListedBot[sender], "You are blacklisted");
        require(!_isBlackListedBot[msg.sender], "You are blacklisted");
        require(!_isBlackListedBot[tx.origin], "You are blacklisted");
        if(sender != owner() && recipient != owner()) {
            require(amount <= _maxTxAmount, "Transfer amount exceeds the maxTxAmount.");
        }
        if(sender != owner() && recipient != owner() && recipient != uniswapV2Pair && recipient != address(0xdead)) {
            uint256 tokenBalanceRecipient = balanceOf(recipient);
            require(tokenBalanceRecipient + amount <= _maxWalletSize, "Recipient exceeds max wallet size.");
        }
        
        uint256 contractTokenBalance = balanceOf(address(this));

        if(contractTokenBalance >= _maxTxAmount) {
            contractTokenBalance = _maxTxAmount;
        }

        bool overMinTokenBalance = contractTokenBalance >= _numOfTokensToExchangeForTeam;
        if (!inSwap && swapEnabled && overMinTokenBalance && sender != uniswapV2Pair) {             
            swapTokensForEth(contractTokenBalance);

            uint256 contractETHBalance = address(this).balance;
            if(contractETHBalance > 0) {
                sendETHToTeam(address(this).balance);
            }
        }
    
        bool takeFee = true;
        
        if(_isExcludedFromFee[sender] || _isExcludedFromFee[recipient]){
            takeFee = false;
        }
    
        _tokenTransfer(sender,recipient,amount,takeFee);
    }

    function transferFrom(address sender, address recipient, uint256 amount) public override returns (bool) {
        _transfer(sender, recipient, amount);
        _approve(sender, _msgSender(), _allowances[sender][_msgSender()].sub(amount, "ERC20: transfer amount exceeds allowance"));
        return true;
    }           
}