/**
 * 	Copyright 2022, Vinícius R. Máximo
 *	Distributed under the terms of the MIT License. 
 *	SPDX-License-Identifier: MIT
 */
package Solution;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.List;

import Data.File;
import Data.Instance;
import Data.Point;
import Improvement.IntraLocalSearch;
import SearchMethod.Config;

public class Solution
{
	private Point points[];
	Instance instance;
	Config config;
	protected int size;
	Node solution[];

	protected int first;
	protected Node depot;
	int capacity;
	public Route routes[];
	public int numRoutes;
	protected int numRoutesMin;
	protected int numRoutesMax;
	public double f = 0;
	public int distance;
	double epsilon;
//	-----------Comparadores-----------

	IntraLocalSearch intraLocalSearch;

	public Solution(Instance instance, Config config)
	{
		this.instance = instance;
		this.config = config;
		this.points = instance.getPoints();
		int depot = instance.getDepot();
		this.capacity = instance.getCapacity();
		this.size = instance.getSize() - 1;
		this.solution = new Node[size];
		this.numRoutesMin = instance.getMinNumberRoutes();
		this.numRoutes = numRoutesMin;
		this.numRoutesMax = instance.getMaxNumberRoutes();
		this.depot = new Node(points[depot], instance);
		this.epsilon = config.getEpsilon();

		this.routes = new Route[numRoutesMax];

		for(int i = 0; i < routes.length; i++)
			routes[i] = new Route(instance, config, this.depot, i);

		int count = 0;
		for(int i = 0; i < (solution.length + 1); i++)
		{
			if(i != depot)
			{
				solution[count] = new Node(points[i], instance);
				count++;
			}
		}
	}

    public Solution loadInitSolution(List<Integer> initSolutionList)
    {
        // 1. Reset global counters
        this.numRoutes = 0;
        this.f = 0;

        // 2. Reset all routes to an empty state
        // Based on the constructor, routes are already initialized with the Depot.
        // We just need to reset their stats and links.
        for (int i = 0; i < routes.length; i++) {
            routes[i].totalDemand = 0;
            routes[i].numElements = 0;
            routes[i].fRoute = 0;
            routes[i].modified = true;

            // Reset the Depot pointers for this route
            // In the constructor, 'routes[i]' was created using 'this.depot'
            // So routes[i].first refers to the Depot node specific to this route (or shared, depending on Route implementation)
            routes[i].first.prev = routes[i].first;
            routes[i].first.next = routes[i].first;
        }

        // 3. Build the solution based on the Integer List
        int currentRouteIndex = 0;

        // Start with the Depot of the first route
        Node prevNode = routes[currentRouteIndex].first;

        // Iterate from index 1 (skipping the first 0 which is the start Depot)
        for (int i = 1; i < initSolutionList.size(); i++) {
            int nodeId = initSolutionList.get(i);

            if (nodeId == 0) { // Assuming 0 is the Depot ID
                // --- END OF ROUTE ---

                // Link the last customer back to the Depot (routes[i].first)
                Node depotNode = routes[currentRouteIndex].first;

                prevNode.next = depotNode;
                depotNode.prev = prevNode;

                this.numRoutes++;

                // Prepare for the next route if there are more nodes
                if (i < initSolutionList.size() - 1) {
                    currentRouteIndex++;
                    prevNode = routes[currentRouteIndex].first; // Reset prevNode to the new route's Depot
                }
            } else {
                // --- CUSTOMER NODE ---

                // Retrieve the existing Node object from the 'solution' array.
                // MAPPING LOGIC: Based on constructor, Customer ID 'k' is at index 'k-1'.
                Node currentNode = this.solution[nodeId - 1];

                // 1. Assign route
                currentNode.route = routes[currentRouteIndex];

                // 2. Link Nodes (Prev <-> Current)
                prevNode.next = currentNode;
                currentNode.prev = prevNode;

                // 3. Update Route Stats
                routes[currentRouteIndex].numElements++;
                // Ensure 'demand' is available in the Node object (loaded from Instance in constructor)
                routes[currentRouteIndex].totalDemand += currentNode.demand;

                // 5. Move pointer
                prevNode = currentNode;
            }
        }

        return this;
    }

	public void clone(Solution reference)
	{
		this.numRoutes = reference.numRoutes;
		this.f = reference.f;

		for(int i = 0; i < routes.length; i++)
		{
			routes[i].nameRoute = i;
			reference.routes[i].nameRoute = i;
		}

		for(int i = 0; i < routes.length; i++)
		{
			routes[i].totalDemand = reference.routes[i].totalDemand;
			routes[i].fRoute = reference.routes[i].fRoute;
			routes[i].numElements = reference.routes[i].numElements;
			routes[i].modified = reference.routes[i].modified;

			if(reference.routes[i].first.prev == null)
				routes[i].first.prev = null;
			else if(reference.routes[i].first.prev.name == 0)
				routes[i].first.prev = routes[i].first;
			else
				routes[i].first.prev = solution[reference.routes[i].first.prev.name - 1];

			if(reference.routes[i].first.next == null)
				routes[i].first.next = null;
			else if(reference.routes[i].first.next.name == 0)
				routes[i].first.next = routes[i].first;
			else
				routes[i].first.next = solution[reference.routes[i].first.next.name - 1];
		}

		for(int i = 0; i < solution.length; i++)
		{
			solution[i].route = routes[reference.solution[i].route.nameRoute];
			solution[i].nodeBelong = reference.solution[i].nodeBelong;

			if(reference.solution[i].prev.name == 0)
				solution[i].prev = routes[reference.solution[i].prev.route.nameRoute].first;
			else
				solution[i].prev = solution[reference.solution[i].prev.name - 1];

			if(reference.solution[i].next.name == 0)
				solution[i].next = routes[reference.solution[i].next.route.nameRoute].first;
			else
				solution[i].next = solution[reference.solution[i].next.name - 1];
		}
	}

	// ------------------------Visualizacao-------------------------

	public String toStringMeu()
	{
		String str = "size: " + size;
		str += "\n" + "depot: " + depot;
		str += "\nnumRoutes: " + numRoutes;
		str += "\ncapacity: " + capacity;

		str += "\nf: " + f;
//		System.out.println(str);
		for(int i = 0; i < numRoutes; i++)
		{
//			System.out.println(str);
			str += "\n" + routes[i];
		}

		return str;
	}

	@Override
	public String toString()
	{
		String str = "";
		for(int i = 0; i < numRoutes; i++)
		{
			str += routes[i].toString2() + "\n";
		}
		str += "Cost " + f + "\n";
		return str;
	}

    public String toListString()
    {
        String str = "[";
        for(int i = 0; i < numRoutes; i++)
        {
            str += routes[i].toListString() + ", ";
        }
        str += "]";
        return str;
    }

	public int infeasibility()
	{
		int capViolation = 0;
		for(int i = 0; i < numRoutes; i++)
		{
			if(routes[i].availableCapacity() < 0)
				capViolation += routes[i].availableCapacity();
		}
		return capViolation;
	}

	public boolean checking(String local, boolean feasibility, boolean emptyRoute)
	{
		double f;
		double sumF = 0;
		int sumNumElements = 0;
		boolean erro = false;

		for(int i = 0; i < numRoutes; i++)
		{
			routes[i].findError();
			f = routes[i].F();
			sumF += f;
			sumNumElements += routes[i].numElements;

			if(Math.abs(f - routes[i].fRoute) > epsilon)
			{
				System.out.println("-------------------" + local + " ERROR-------------------" + "\n" + routes[i].toString() + "\nf esperado: " + f);
				erro = true;
			}

			if(emptyRoute && routes[i].first == routes[i].first.next)
			{
				System.out.println("-------------------" + local + " ERROR-------------------" + "Empty route: " + routes[i].toString());
				erro = true;
			}

			if(routes[i].first.name != 0)
			{
				System.out.println("-------------------" + local + " ERROR-------------------" + " Route initiating without depot: " + routes[i].toString());
				erro = true;
			}

			if(feasibility && !routes[i].isFeasible())
			{
				System.out.println("-------------------" + local + " ERROR-------------------" + "Infeasible route: " + routes[i].toString());
				erro = true;
			}

		}
		if(Math.abs(sumF - this.f) > epsilon)
		{
			erro = true;
			System.out.println("-------------------" + local + " Error total sum-------------------");
			System.out.println("Expected: " + sumF + " obtained: " + this.f);
			System.out.println(this.toStringMeu());
		}

		if((sumNumElements - numRoutes) != size)
		{
			erro = true;
			System.out.println("-------------------" + local + " ERROR quantity of Elements-------------------");
			System.out.println("Expected: " + size + " obtained : " + (sumNumElements - numRoutes));

			System.out.println(this);
		}
		return erro;
	}

	public boolean feasible()
	{
		for(int i = 0; i < numRoutes; i++)
		{
			if(routes[i].availableCapacity() < 0)
				return false;
		}
		return true;
	}

	public void removeEmptyRoutes()
	{
		for(int i = 0; i < numRoutes; i++)
		{
			if(routes[i].first == routes[i].first.next)
			{
				removeRoute(i);
				i--;
			}
		}
	}

	private void removeRoute(int index)
	{
		Route aux = routes[index];
		if(index != numRoutes - 1)
		{
			routes[index] = routes[numRoutes - 1];

			routes[numRoutes - 1] = aux;
		}
		numRoutes--;
	}

	public void uploadSolution(String name)
	{
		BufferedReader in;
		try
		{
			in = new BufferedReader(new FileReader(name));
			String str[] = null;
			String line;

			line = in.readLine();
			str = line.split(" ");

			for(int i = 0; i < 3; i++)
				in.readLine();

			int indexRoute = 0;
			line = in.readLine();
			str = line.split(" ");

			System.out.println("-------------- str.length: " + str.length);
			for(int i = 0; i < str.length; i++)
			{
				System.out.print(str[i] + "-");
			}
			System.out.println();

			do
			{
				routes[indexRoute].addNodeEndRoute(depot.clone());
				for(int i = 9; i < str.length - 1; i++)
				{
					System.out.println("add: " + solution[Integer.valueOf(str[i].trim()) - 1] + " na route: " + routes[indexRoute].nameRoute);
					f += routes[indexRoute].addNodeEndRoute(solution[Integer.valueOf(str[i]) - 1]);
				}
				indexRoute++;
				line = in.readLine();
				if(line != null)
					str = line.split(" ");
			}
			while(line != null);

		}
		catch(IOException e)
		{
			System.out.println("File read Error");
		}
	}

	public void uploadSolution1(String name)
	{
		BufferedReader in;
		try
		{
			in = new BufferedReader(new FileReader(name));
			String str[] = null;

			str = in.readLine().split(" ");
			int indexRoute = 0;
			while(!str[0].equals("Cost"))
			{
				for(int i = 2; i < str.length; i++)
				{
					f += routes[indexRoute].addNodeEndRoute(solution[Integer.valueOf(str[i]) - 1]);
				}
				indexRoute++;
				str = in.readLine().split(" ");
			}
		}
		catch(IOException e)
		{
			System.out.println("File read Error");
		}
	}

	public Route[] getRoutes()
	{
		return routes;
	}

	public int getNumRoutes()
	{
		return numRoutes;
	}

	public Node getDepot()
	{
		return depot;
	}

	public Node[] getSolution()
	{
		return solution;
	}

	public int getNumRoutesMax()
	{
		return numRoutesMax;
	}

	public void setNumRoutesMax(int numRoutesMax)
	{
		this.numRoutesMax = numRoutesMax;
	}

	public int getNumRoutesMin()
	{
		return numRoutesMin;
	}

	public void setNumRoutesMin(int numRoutesMin)
	{
		this.numRoutesMin = numRoutesMin;
	}

	public int getSize()
	{
		return size;
	}

	public void printSolution(String end)
	{
		File arq = new File(end);
		arq.write(this.toString());
		arq.close();
	}

}
