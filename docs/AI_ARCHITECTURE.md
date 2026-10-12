# AI Architecture

This project uses classical, explainable AI instead of opaque black-box prediction. Every important decision is paired with reasoning that a command-center officer can inspect.

## Intelligent Agents

### Purpose

Agents are autonomous decision modules that handle one part of the crisis workflow.

### Input

Each agent receives observations such as emergency type, flood severity, team status, road conditions, or resource availability.

### Output

Each agent emits a structured decision, such as a risk report, route recommendation, or resource recommendation.

### ResQAI usage

- Risk Agent: estimates incident danger and flood exposure
- Routing Agent: calculates the path to a shelter or hospital
- Resource Agent: selects available ambulances and kits
- Shelter Agent: chooses the operation-friendly shelter
- Medical Agent: confirms whether ambulance and hospital support are needed
- Command Agent: consolidates the final response plan

### Example

A flood with high rainfall and medical assistance triggers the Risk Agent, Routing Agent, and Medical Agent in sequence before the Command Agent issues the final plan.

## Knowledge-Based Systems

### Purpose

Represent domain rules in a form that can be inspected and explained.

### Input

Observed facts such as flood_level, medical_assistance, rainfall, or people_affected.

### Output

Derived facts and clear rule explanations.

### ResQAI usage

Rules in the backend define when high_risk, critical_priority, ambulance_required, and hospital_required become true.

### Example

IF flood_level = high THEN high_risk = true.

## Forward Chaining

### Purpose

Start from observed facts and repeatedly apply rules until no new facts can be derived.

### Input

Current incident facts.

### Output

Derived conclusions and the rule trace.

### ResQAI usage

The forward chain infers critical priority and required medical support for flood emergencies.

### Example

flood_level = high + medical_assistance = true => critical_priority = true

## Backward Chaining

### Purpose

Check whether a goal is supported by evidence.

### Input

A question such as "Is hospital support required?"

### Output

A reasoning chain proving or disproving the goal.

### ResQAI usage

The backend can trace hospital_required back to medical_assistance and the relevant risk state.

### Example

hospital_required -> medical_assistance -> true

## BFS

### Purpose

Find the shortest path in terms of number of hops when the cost is uniform.

### Input

Graph nodes and edges.

### Output

A valid shortest-hop route.

### ResQAI usage

This is a useful baseline pathfinder in routing experiments, although A\* is the primary route choice for the demo.

## DFS

### Purpose

Explore one route branch deeply before backtracking.

### Input

Graph and start node.

### Output

A path that can be found quickly but not necessarily at minimum cost.

### ResQAI usage

The codebase keeps DFS available as a concept for route exploration and comparison with A\*.

## Uniform Cost Search

### Purpose

Expand the lowest cumulative cost edge first.

### Input

Weighted graph with distance and risk costs.

### Output

Minimum cost path under a cost function.

### ResQAI usage

Useful for comparing the route model with weighted A\* when different costs are considered.

## A\*

### Purpose

Combine path cost and heuristic estimate to find efficient routes quickly.

### Input

Start node, target, graph, and heuristic values.

### Output

Chosen route, cost, and ETA.

### ResQAI usage

This is the primary route algorithm in the ResQAI demo, balancing distance, time, flood risk, and blockage penalties.

### Example

citizen -> junction_a -> junction_b -> shelter_07

## Greedy Best-First Search

### Purpose

Select the node with the lowest heuristic estimate first.

### Input

Heuristic function and frontier.

### Output

A plausible but not always globally optimal route.

### ResQAI usage

The example routing logic can be compared against A\* when choosing the best emergency path.

## Heuristic Search

### Purpose

Estimate remaining effort to reach the destination without exploring full search space.

### Input

Current node and target.

### Output

A heuristic score used by algorithms like A\*.

### ResQAI usage

The route model uses a simple estimated-distance heuristic to prioritize safer and faster emergency paths.

## Online Search

### Purpose

Handle a changing environment while the rescue is underway.

### Input

Current route, current location, and road conditions.

### Output

New route and revised ETA.

### ResQAI usage

When a road becomes blocked, the system invalidates the current route and recalculates an alternative path.

## Partially Observable Environment

### Purpose

Reason with unknown information without assuming the unsafe state is safe.

### Input

Road status such as SAFE, UNKNOWN, or BLOCKED.

### Output

Higher uncertainty and a more conservative risk score.

### ResQAI usage

Unknown road segments add an uncertainty penalty to the Bayesian risk estimate.

## Bayesian Reasoning

### Purpose

Estimate the likelihood of an unsafe condition based on multiple factors.

### Input

Rainfall, flood level, river proximity, citizen flood reports, and road status.

### Output

Probability, risk label, and evidence list.

### ResQAI usage

The system labels risk as LOW, MEDIUM, HIGH, or CRITICAL and shows the evidence behind it.

### Example

High rainfall + high river proximity + multiple reports -> HIGH risk and explainable reasoning.

## Constraint Satisfaction Problems

### Purpose

Select a feasible option satisfying all hard constraints.

### Input

Candidate shelters, teams, and resources.

### Output

Feasible matches and the chosen best option.

### ResQAI usage

Shelter selection checks capacity, distance, status, and medical support. Team selection checks skills and vehicle suitability.

## Local Search / Optimization

### Purpose

Improve a candidate solution by scoring alternatives.

### Input

Available teams and objective criteria.

### Output

A ranked best-fit solution.

### ResQAI usage

The team allocation logic scores each team by ETA, distance, skill match, and medical capability.

## Multi-Agent Systems

### Purpose

Split the rescue decision into specialist roles that interact via structured messages.

### Input

Emergency facts and operational state.

### Output

A coordinated response plan.

### ResQAI usage

The architecture includes a Risk Agent, Routing Agent, Resource Agent, Shelter Agent, Medical Agent, and Command Agent.

## Dynamic Replanning

### Purpose

Recalculate a route after new information affects the plan.

### Input

Current route, current location, destination, and road conditions.

### Output

Alternative route, revised ETA, and reason for rerouting.

### ResQAI usage

When Junction B becomes blocked, the system chooses a safe alternative and updates the officer and citizen views.

## Summary

The project demonstrates explainable AI in a realistic disaster response scenario. The combination of transparent rules, Bayesian reasoning, pathfinding, and dynamic replanning makes it easy for judges and students to understand the system while still producing a compelling demo.
