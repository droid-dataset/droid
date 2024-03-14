---
layout: default
title: Evaluating Policies
parent: Example Workflows
nav_order: 5
---

# Evaluating Policies

* Run a variant of [this](https://github.com/droid-dataset/droid/blob/main/scripts/evaluation/evaluate_policy.py) file with the desired properties.
	* Make sure to update policy_logdir and model_id with the desired values
	* Any properties that are added to the variant will be loaded from the training folder values.
* It is recommended to start off by evaluating policies in the “Practice” tab for simplicity.
* Note: The robot will only move when you are holding down the side button of the controller. However, instead of the actions coming from your handle as during data collection, the actions will come from the policy.

