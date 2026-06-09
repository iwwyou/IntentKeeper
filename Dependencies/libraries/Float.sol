pragma solidity ^0.8.0;

struct FloatStruct {
    uint256 numerator;
    uint256 denominator;
}

library Float {
    function multiply(uint256 a, FloatStruct memory f) internal pure returns(uint256) {
        require(f.denominator != 0, "div 0");
        return a * f.numerator / f.denominator;
    }

    function inverse(FloatStruct memory f) internal pure returns(FloatStruct memory) {
        require(f.numerator != 0 && f.denominator != 0, "div 0");
        return FloatStruct({
            numerator: f.denominator,
            denominator: f.numerator
        });
    }

    function divide(uint256 a, FloatStruct memory f) internal pure returns(uint256) {
        require(f.denominator != 0, "div 0");
        return a * f.denominator / f.numerator;
    }

    function add(FloatStruct memory a, FloatStruct memory b) internal pure returns(FloatStruct memory res) {
        require(a.denominator != 0 && b.denominator != 0, "div 0");
        res = FloatStruct({
            numerator : a.numerator*b.denominator + a.denominator*b.numerator,
            denominator : a.denominator*b.denominator
        });
        if(res.numerator > 2**128 && res.denominator > 2**128){
            res.numerator = res.numerator / 2**64;
            res.denominator = res.denominator / 2**64;
        }
    }

    function sub(FloatStruct memory a, FloatStruct memory b) internal pure returns(FloatStruct memory res) {
        require(a.denominator != 0 && b.denominator != 0, "div 0");
        res = FloatStruct({
            numerator : a.numerator*b.denominator - b.numerator*a.denominator,
            denominator : a.denominator*b.denominator
        });
        if(res.numerator > 2**128 && res.denominator > 2**128){
            res.numerator = res.numerator / 2**64;
            res.denominator = res.denominator / 2**64;
        }
    }

    function mul(FloatStruct memory a, FloatStruct memory b) internal pure returns(FloatStruct memory res) {
        require(a.denominator != 0 && b.denominator != 0, "div 0");
        res = FloatStruct({
            numerator : a.numerator * b.numerator,
            denominator : a.denominator * b.denominator
        });
        if(res.numerator > 2**128 && res.denominator > 2**128){
            res.numerator = res.numerator / 2**64;
            res.denominator = res.denominator / 2**64;
        }
    }

    function gt(FloatStruct memory a, FloatStruct memory b) internal pure returns(bool) {
        require(a.denominator != 0 && b.denominator != 0, "div 0");
        return a.numerator * b.denominator > a.denominator * b.numerator;
    }

    function lt(FloatStruct memory a, FloatStruct memory b) internal pure returns(bool) {
        require(a.denominator != 0 && b.denominator != 0, "div 0");
        return a.numerator * b.denominator < a.denominator * b.numerator;
    }

    function gte(FloatStruct memory a, FloatStruct memory b) internal pure returns(bool) {
        require(a.denominator != 0 && b.denominator != 0, "div 0");
        return a.numerator * b.denominator >= a.denominator * b.numerator;
    }

    function lte(FloatStruct memory a, FloatStruct memory b) internal pure returns(bool) {
        require(a.denominator != 0 && b.denominator != 0, "div 0");
        return a.numerator * b.denominator <= a.denominator * b.numerator;
    }

    function equals(FloatStruct memory a, FloatStruct memory b) internal pure returns(bool) {
        require(a.denominator != 0 && b.denominator != 0, "div 0");
        return a.numerator * b.denominator == b.numerator * a.denominator;
    }
}
